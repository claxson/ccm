# -*- coding: utf-8 -*-

from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.shortcuts import render

from urllib import urlencode
from httplib2 import Http

import json
from time import time
from datetime import date
from datetime import datetime

from misc import post_to_promiscuus

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# App Models
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from models import User, UserPayment, PaymentHistory, Currency, Integrator, Country, IntegratorSetting, Package, Setting

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Response Codes
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
http_POST_OK              = 201
http_REQUEST_OK           = 200
http_NOT_FOUND            = 404
http_BAD_REQUEST          = 400
http_UNPROCESSABLE_ENTITY = 422
http_NOT_ALLOWED          = 405
http_UNAUTHORIZED         = 401
http_PAYMENT_REQUIRED     = 402
http_INTERNAL_ERROR       = 500

def __validate_json(json_data, keys):
    for key in keys:
        if key not in json_data:
            message = "missing key in json: %s" % key
            return {'status': 'error', 'message': message}

    return {'status': 'success'}
    
def __check_apikey(request):
    if 'HTTP_X_AUTH_CCM_KEY' in request.META:
        if request.META['HTTP_X_AUTH_CCM_KEY'] == Setting.get_var('ma_apikey'):
            return {'status': 'success'}
        else:
            return {'status': 'error'}
    else:
        return {'status': 'error'}    


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Devuelve JSON con URL de formulario de pago                                 #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Parametros: user_id, email, recurrence                                                                     #
# Retorno: url                                                                                               #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@require_http_methods(["POST"])
def payment_commercegate(request):
    # Verifico ApiKey
    cap = __check_apikey(request)
    if cap['status'] == 'error':
        return HttpResponse(status=http_UNAUTHORIZED)
    
    # Cargo el JSON
    try:
        data = json.loads(request.body)
    except Exception:
        message = 'error decoding json'
        body = { 'status': 'error', 'message': message }

        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)
    
    # Verifico las key mandatorias
    keys = [ 'user_id', 'email', 'recurrence' ]

    json_loader = __validate_json(data, keys)

    if json_loader['status'] == 'error':
        json_loader['message'] = 'Ocurrió un error con el pago, por favor reintente nuevamente más tarde'

        return HttpResponse(json.dumps(json_loader), content_type='application/json', status=http_BAD_REQUEST)

    # Obtengo pais
    country = Country.get_by_code(data['user_id'].split("_")[0].lower())

    # Obtengo Integrador
    integrator = Integrator.get_by_country('commerce_gate', country)
    if integrator is None:
        message = "integrator does not exist for country %s" % country.name
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    # Obtengo Integrator Settings
    redirect_url_failed  = IntegratorSetting.get_var(integrator, 'redirect_url_failed')
    redirect_url_success = IntegratorSetting.get_var(integrator, 'redirect_url_success')
    endpoint             = IntegratorSetting.get_var(integrator, 'endpoint')
    endpoint_token       = IntegratorSetting.get_var(integrator, 'endpoint_token')
    website_id           = IntegratorSetting.get_var(integrator, 'website_id')
    customer_id          = IntegratorSetting.get_var(integrator, 'customer_id')

    # Verifico si el usuario existe y sino lo creo
    try:
        user = User.objects.get(user_id=data['user_id'])
        user.email = data['email']
        user.save()
    except ObjectDoesNotExist:
        user = User.create(data['user_id'], data['email'], integrator.country)

    # Obtengo el paquete
    if 'package_id' in data:
        package = Package.get_by_id(data['package_id'], integrator)
    else:
        package = Package.get(data['recurrence'], integrator)

    if package is None:
        message = "package not found with that duration"
        body = { 'status': 'error', 'message': message }

        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    # Si tiene algun UserPayment habilitado devuelvo un error
    up = UserPayment.get_active(user)
    if up is not None:
        message = 'enabled user payment already exists'
        body = { 'status': 'error', 'message': message }
        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)
    else:    
        up = UserPayment.create_from_package(user, package)

    payment_id = "PH_%s_%d" % (user.user_id, int(time()))

    # Creo el PaymentHistory
    ph = PaymentHistory.create(up, payment_id, integrator)

    params = { 'cid': customer_id, 'wid': website_id, 'packid': package.package_id, 'username': data['user_id'], 'email': data['email']  }
    url = '%s?%s' % (endpoint_token, urlencode(params))
    
    try:
        resp, content = Http().request(url, 'POST')
    except Exception as e:
        message = "communication error with commercegate, waiting callback"
        body = { 'status': 'error', 'message': message }

        return HttpResponse(json.dumps(body), content_type="application/json", status=http_PAYMENT_REQUIRED)

    iframe_params = { 'cid': customer_id, 'wid': website_id, 'token': content }

    if redirect_url_success:
        iframe_params['successUrl'] = redirect_url_success

    if redirect_url_failed:
        iframe_params['failedUrl'] = "%s://%s/commercegate/error/%s" % (request.scheme, request.META['HTTP_HOST'], up.user_payment_id)
    
    iframe_url = '%s?%s' % (endpoint, urlencode(iframe_params))
    body = { 'status': 'success', 'value': { 'url': iframe_url } }

    return HttpResponse(json.dumps(body), content_type="application/json", status=http_POST_OK)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Cancela usuario                                                             #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Parametros: user_id                                                                                        #
# Retorno: status                                                                                            #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@require_http_methods(["POST"])
def cancel_commercegate(request):
    # Cargo el JSON
    try:
        data = json.loads(request.body)
    except Exception:
        message = 'error decoding json'
        body = { 'status': 'error', 'message': message }

        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)

    # Verifico las key mandatorias
    keys = [ 'user_id' ]

    json_loader = __validate_json(data, keys)

    if json_loader['status'] == 'error':
        json_loader['message'] = 'check api mandatory parameters'
        return HttpResponse(json.dumps(json_loader), content_type='application/json', status=http_BAD_REQUEST)

    # Obtengo pais
    country = Country.get_by_code(data['user_id'].split("_")[0].lower())

    # Obtengo Integrador
    integrator = Integrator.get_by_country('commerce_gate', country)
    if integrator is None:
        message = "integrator does not exist for country %s" % country.name
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    # Obtengo Integrator Settings
    endpoint_cancel      = IntegratorSetting.get_var(integrator, 'endpoint_cancel')
    customer_id          = IntegratorSetting.get_var(integrator, 'customer_id')
    password             = IntegratorSetting.get_var(integrator, 'password')

    # Verifico que el usuario existe o no este ya cancelado
    try:
        user = User.objects.get(user_id=data['user_id'])
    except ObjectDoesNotExist:
        message = 'user not found'
        body = { 'status': 'error', 'message': message }

        return HttpResponse(json.dumps(body), content_type='application/json', status=http_NOT_FOUND)

    if not user.is_active:
        message = 'already canceled user'
        body = { 'status': 'error', 'message': message }

        return HttpResponse(json.dumps(body), content_type='application/json', status=http_NOT_FOUND)

    up = UserPayment.get_active(user=user)
    if up is None:
        message = "user_id %s has not enabled recurring payment" % data['user_id']
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    ph = PaymentHistory.get_first_approved(up)
    if ph is None:
        message = "there isnt approved payments for userpayment_id %s" % up.user_payment_id
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    #params = { 'customerId': customer_id, 'websiteId': website_id, 'password': password, 'username': data['user_id'] }
    params = { 'customerId': customer_id, 'password': password, 'first_transaction_id': ph.gateway_id }
    url = '%s?%s' % (endpoint_cancel, urlencode(params))

    # Llamo a la api de commercegate
    try:
        resp, content = Http().request(url, 'POST')
    except Exception as e:
        message = 'communication error with commercegate'
        body = { 'status': 'error', 'message': e }
        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)

    body = { 'status': 'success' }
    return HttpResponse(json.dumps(body), content_type='application/json', status=http_POST_OK)


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Error en pago                                                               #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Parametros: user_payment_id                                                                                #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@require_http_methods(["GET"])
def error_commercegate(request, user_payment_id):
    up = UserPayment.get_by_id(user_payment_id)
    template = 'error/paymenterror.html'
    if up is not None:
        if 'errMsg' in request.GET and 'errNum' in request.GET:
            message = "code: %s - message: %s" % (request.GET['errNum'], request.GET['errMsg'])
        else:
            message = ''
        up.reply_error(message)
        ph = PaymentHistory.get(up, 'P')
        if ph is not None:
            ph.reject('', message)

            # POST to promiscuus
            resp_promiscuus = post_to_promiscuus(ph, 'payment_commit')
            if resp_promiscuus['status'] == 'error':
                ph.message = "%s - Promiscuus error: %s" % (ph.message, resp_promiscuus['message'])
                ph.save()

    # Obtengo Integrator Settings
    redirect_url_failed  = IntegratorSetting.get_var(ph.integrator, 'redirect_url_failed')

    context = {'redirect_url': redirect_url_failed}
    return render(request, template, context)
    




