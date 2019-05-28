# -*- coding: utf-8 -*-

from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist

from urllib import urlencode
from httplib2 import Http

import json
from time import time
from datetime import date
from datetime import datetime

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# App Models
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from models import User, UserPayment, PaymentHistory, Currency, Integrator, Country, IntegratorSetting, Package

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


# Integrator Settings
integrator           = Integrator.get('commerce_gate')
redirect_url_failed  = IntegratorSetting.get_var(integrator, 'redirect_url_failed')
redirect_url_success = IntegratorSetting.get_var(integrator, 'redirect_url_success')
endpoint             = IntegratorSetting.get_var(integrator, 'endpoint')
endpoint_token       = IntegratorSetting.get_var(integrator, 'endpoint_token')
endpoint_cancel      = IntegratorSetting.get_var(integrator, 'endpoint_cancel')
website_id           = IntegratorSetting.get_var(integrator, 'website_id')
customer_id          = IntegratorSetting.get_var(integrator, 'customer_id')
password             = IntegratorSetting.get_var(integrator, 'password')

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

    # Verifico si el usuario existe y sino lo creo
    try:
        user       = User.objects.get(user_id=data['user_id'])
        user.email = data['email']
        user.save()
    except ObjectDoesNotExist:
        user = User.create(data['user_id'], data['email'], integrator.country)

    package = Package.get(data['recurrence'], integrator)

    if package is None:
        message = "package not found with that duration"
        body = { 'status': 'error', 'message': message }

        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    country = Country.get(integrator.country)

    # Si tiene algun UserPayment habilitado devuelvo un error
    try:
        up = UserPayment.objects.get(user=user, enabled=True)
        if up.status == 'AC':
            message = 'enabled user payment already exists'
            body = { 'status': 'error', 'message': message }

            return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)
    except ObjectDoesNotExist:
        up = UserPayment.create(user, package.duration, package.amount, country.currency)

    payment_id = "PH_%s_%d" % (user.user_id, int(time()))

    # Si existe PaymentHistory lo uso sino lo creo
    try:
        ph = PaymentHistory.objects.get(user_payment=up, status='P')
    except ObjectDoesNotExist:
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
        iframe_params['failedUrl'] = redirect_url_failed

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

    params = { 'customerId': customer_id, 'websiteId': website_id, 'password': password, 'username': data['user_id'] }
    url = '%s?%s' % (endpoint_cancel, urlencode(params))

    # Llamo a la api de commercegate
    try:
        resp, content = Http().request(url, 'POST')
    except Exception:
        message = 'communication error with commercegate'
        body = { 'status': 'error', 'message': message }

        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)

    body = { 'status': 'success' }
    return HttpResponse(json.dumps(body), content_type='application/json', status=http_POST_OK)