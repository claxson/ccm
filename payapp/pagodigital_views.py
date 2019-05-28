# -*- coding: utf-8 -*-

from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render

import json
from time import time
from urllib import urlencode
from datetime import datetime

from models import User
from models import UserPayment
from models import PaymentHistory
from models import Integrator
from models import Country 
from models import Package
from models import Setting
from models import Form
from models import Card

from misc import post_to_intercom

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
        if json_data[key] is None or json_data[key] == '':
            message = "invalid value in key: %s" % key
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
     
     
def __payday_calc(payment_date):
    if payment_date == 0 or payment_date == 0.0 or payment_date == "0":
        payment_date = time()
    day = datetime.fromtimestamp(int(payment_date)).strftime('%d')
    if int(day) > 28:
        return 28
    else:
        return int(day)


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Devuelve JSON con URL de formulario de pago                                 #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Parametros:                                                                                                #
#     - Mandatorios: user_id, email, payment_date, recurrence                                                #
#     - Opcionales: discount, disc_counter                                                                   #
# Retorno: url                                                                                               #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@require_http_methods(["POST"])
def payment_pagodigital(request):
    # Vars
    integrator = Integrator.get('pagodigital')
    baseurl    = Setting.get_var('baseurl')
    template   = 'pagodigital.html'

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
    keys = [ 'user_id', 'email', 'payment_date','recurrence' ]
    json_loader = __validate_json(data, keys)

    if json_loader['status'] == 'error':
        return HttpResponse(json.dumps(json_loader), content_type='application/json', status=http_BAD_REQUEST)

    # Verifico si el usuario existe y sino lo creo
    try:
        user       = User.objects.get(user_id=data['user_id'])
        user.email = data['email']
        user.save()
    except ObjectDoesNotExist:
        user = User.create(data['user_id'], data['email'], integrator.country)

    # Verifico que no tenga un User Payment activo
    up = UserPayment.get_active(user)
    if up is not None:
        message = 'enabled user payment already exists'
        body = { 'status': 'error', 'message': message }
        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)
    
    package = Package.get(data['recurrence'], integrator)
    if package is None:
        message = "package not found with that duration"
        body = { 'status': 'error', 'message': message }
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
        
    # Creo UserPayment
    payday = __payday_calc(data['payment_date'])
    up = UserPayment.create(user, 
                            package.duration,
                            package.amount,
                            integrator.country.currency,
                            data['payment_date'],
                            payday,
                            0,
                            0,
                            True)

    # Aplico descuento si existe
    if 'discount' in data and 'disc_counter' in data:
        up.discount(data['discount'], data['disc_counter'])

    # Creo el form
    form = Form.create(user, integrator, package, template)
    if form is None:
        message = "form could not be created"
        body = { 'status': 'error', 'message': message }
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)        
        
    iframe_params = { 'user_id': user.user_id, 'token': form.token }
    iframe_url    = '%sapi/v1/pagodigital/form/?%s' % (baseurl, urlencode(iframe_params))
    body = { 'status': 'success', 'value': { 'url': iframe_url } }

    return HttpResponse(json.dumps(body), content_type="application/json", status=http_POST_OK)
    
    
    
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Devuelve JSON con URL de formulario de pago                                 #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ---------- POST ---------                                                                                  #
# Parametros (POST JSON):                                                              # 
# ---------- GET ----------                                                                                  #
# Parametros: user_id, token                                                                                 #
# Retorno: url                                                                                               #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++



@require_http_methods(["GET", "POST"])
def form_pagodigital(request):
    if request.method == 'POST':  
        data = request.POST
        # Verifico las key mandatorias
        keys = [ 'name', 'phone', 'address', 'id_card', 'email', 'city', 
                 'state', 'cc_number', 'cc_exp_year', 'cc_exp_year', 
                 'cc_cvv', 'cc_fr_number', 'cc_fr_name', 'token', 'user_id' ]
        json_loader = __validate_json(request.POST, keys)
        if json_loader['status'] == 'error':
            return HttpResponse(json.dumps(json_loader), content_type='application/json', status=http_BAD_REQUEST)
        
        user = User.get(data['user_id'])
        form = Form.get(user, data['token'])
        if form is None:
            message = 'form not available'
            body = { 'status': 'error', 'message': message }
            return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)
        
        # Verifico que no tenga un User Payment activo
        up = UserPayment.get_enabled(user)
        if up is not None:
            if up.status != 'PE':
                message = 'enabled user payment already exists'
                body = { 'status': 'error', 'message': message }
                return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)
        
        # Realizar add card y obtener token
        # ---- Hace librería para pago digital ----
        card_token = "123455666"
        
        # Deshabilito cualquier tarjeta existente
        cards = Card.objects.filter(user=user, enabled=True)
        for card in cards:
            card.disable()
        
        # Creo la tarjeta o la obtengo si ya existe
        card = Card.get_by_token(up.user, card_token)
        card.enable()
        if card is None:
            card_exp = "%s/%s" % (data['cc_exp_month'], data['cc_exp_year'][-2:])
            card = Card.create_with_token(user, card_token, data['cc_number'][-4:], card_exp, data['cc_fr_name'], form.integrator)
        
        # Aplico descuento si corresponde
        disc_flag = False
        if up.disc_counter > 0:
            disc_flag = True
            disc_pct = up.disc_pct
        else:
            disc_pct = 0

        # Genero tx id sumando al userid el timestamp
        payment_id = "PH_%s_%d" % (user.user_id, int(time()))

        # Creo el registro en PaymentHistory
        ph = PaymentHistory.create(up, payment_id, form.integrator, card, disc_pct)

        if ph.amount > 0:
            # Realizar pago
            pd_endpoint = IntegratorSetting.get_var(form.integrator, 'endpoint')
            pd_user     = IntegratorSetting.get_var(form.integrator, 'user')
            pd_password = IntegratorSetting.get_var(form.integrator, 'password')
            try:
                # ---- Hacer librería para pago digital ----
                pass
            except Exception as e:
                # ---------- Analizar que pasa ante un error en el pago ---------------
                # Pongo el pago en Waiting Callback
                ph.status = "W"
                ph.save()
                return False
        else:
            ret = True
            content = {'transaction': {'status_detail':'-10', 'id':'-10', 'message': 'Pago con descuento del 100%'}}       
     
        if ret:
            # Obtengo los valores segun la respuesta de Pagodigital
            pr = pagodigital_translator(content)
            # Seteo los valores de la UserPayment
            up.status  = pr["up_status"]
            up.message = pr["up_message"]
            up.enabled = pr["up_recurrence"]

            if up.status == 'AC':
                # calcular next_payment_day
                up.payment_date = up.calc_payment_date()
                # Fija la fecha de expiration del usuario
                user.set_expiration(up.payment_date)
                if disc_flag:
                    up.disc_counter = up.disc_counter - 1
            else:
                up.channel = 'R'
            up.save()
            
            

            # Seteo los valores del PaymentHistory
            ph.status     = pr["ph_status"]
            ph.gateway_id = pr["ph_gatewayid"]
            ph.message    = pr["ph_message"]
            ph.save()

            if ph.status == 'A':
                rep_status = "success"
            else:
                rep_status = "error"

            if pr["user_expire"]:
                user.expire()
                
            # Posteo en intercomo si es requerido
            if pr["intercom"]["action"]:
                ph = post_to_intercom(ph, pr["intercom"]["event"], paymentez_intercom_metadata(content['transaction']))               

            body = {'status': rep_status, 'message': '', 'user_message': pr['user_message']}
            print "################### Subscripcion OK ###############"
            print body
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_POST_OK)
        
        else:
            user_message = "Ocurrió un error con el pago, por favor consulte con el banco emisor de la tarjeta y reintente nuevamente más tarde"
            message = "could not create user payment: (Unknown Integrator: %s)" % str(form.integrator.name)
            body = {'status': 'error', 'message': message, 'user_message': user_message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)   
        
        
        
        
    elif request.method == 'GET':
        print request.GET
        user = User.get(request.GET['user_id'])
        template = Form.get_template(user, request.GET['token'])
        if template is None:
            message = 'form not available'
            body = { 'status': 'error', 'message': message }
            return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)
        
        context = {'country': user.country.code}
        print template
        print context
        return render(request, template, context)
        
            
            
        