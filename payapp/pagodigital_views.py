# -*- coding: utf-8 -*-

from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt

import json
from time import time
from time import mktime
from urllib import urlencode
from datetime import datetime

from models import User
from models import UserPayment
from models import PaymentHistory
from models import Integrator
from models import IntegratorSetting
from models import Country 
from models import Package
from models import Setting
from models import Form
from models import Card

#from misc import post_to_intercom
from misc import pagodigital_translator
#from misc import pagodigital_intercom_metadata
from misc import unicodetoascii
from misc import post_to_promiscuus

from pagodigital import PagoDigitalGateway
from pagodigital import PagoDigitalCard
from pagodigital import PagoDigitalTx
from pagodigital import PagoDigitalJWTGateway

#from payapp.intercom import Intercom

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

SUCCESS_CODES = ['000', '002', '003', '004', '005', '006', '007', '008', '009',
                 '00', '08', '11', '76', '77', '78', '79', '80', '81']


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
    template   = 'pagodigital/pagodigital.html'

    # Verifico ApiKey
    cap = __check_apikey(request)
    if cap['status'] == 'error':
        return HttpResponse(status=http_UNAUTHORIZED)
    
    # Cargo el JSON
    try:
        data = json.loads(request.body)
        print "CONTENT MA: %s" % data
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
        if up.enabled_card:
            message = 'enabled user payment already exists'
            body = { 'status': 'error', 'message': message }
            return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)
        else:
            up.status = 'PE'
            up.save()
    
    # Obtengo el paquete
    if 'package_id' in data:
        package = Package.get_by_id(data['package_id'], integrator)
    else:
        package = Package.get(data['recurrence'], integrator)
        
    if package is None:
        message = "package not found with that duration"
        body = { 'status': 'error', 'message': message }
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
    

    # Creo UserPayment
    up = UserPayment.create_from_package(user, package, data['payment_date'], 0, 0, True)

    # Aplico descuento si existe
    if 'discount' in data and 'disc_counter' in data:
        up.discount(data['discount'], data['disc_counter'])

    # Creo el form
    form = Form.create(user, up, integrator, template, 'UP', package)
    if form is None:
        message = "form could not be created"
        body = { 'status': 'error', 'message': message }
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)        
        
    iframe_params = { 'user_id': user.user_id, 'token': form.token }
    iframe_url    = '%sapi/v1/pagodigital/userpayment/form/?%s' % (baseurl, urlencode(iframe_params))
    body = { 'status': 'success', 'value': { 'url': iframe_url } }

    return HttpResponse(json.dumps(body), content_type="application/json", status=http_POST_OK)
    
    
    
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Crea el UserPayment y realiza el addcard y pago                             #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ---------- POST ---------                                                                                  #
# Parametros (POST JSON):                                                                                    # 
# ---------- GET ----------                                                                                  #
# Parametros: user_id, token                                                                                 #
# Retorno: url                                                                                               #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@xframe_options_exempt
@require_http_methods(["GET", "POST"])
def userpayment_form_pagodigital(request):
    ########  Metodo POST  ########
    if request.method == 'POST':  
        data = request.POST
        template = 'pagodigital/redirect.html'
        
        # Verifico las key mandatorias
        keys = [ 'name', 'phone', 'address', 'id_card', 'email', 'city', 
                 'state', 'cc_number', 'cc_exp_month', 'cc_exp_year', 
                 'cc_cvv', 'cc_fr_number', 'cc_fr_name', 'user_id' , 'token']
                
        json_loader = __validate_json(data, keys)
        if json_loader['status'] == 'error':
            return HttpResponse(json.dumps(json_loader), content_type='application/json', status=http_BAD_REQUEST)
        
        # Obtengo el usuario y el form vinculado al token
        user = User.get(data['user_id'])
        form = Form.get(user, data['token'])
        if form is None:
            message = 'form not available'
            body = { 'status': 'error', 'message': message }
            return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)

        # Verifico que no tenga un User Payment activo
        active_up = UserPayment.get_active(user)
        if active_up is not None:
            message = 'enabled user payment already exists'
            body = { 'status': 'error', 'message': message }
            return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)
        
        up = form.user_payment
        
        # Obtengo settings del integrator
        api_key = IntegratorSetting.get_var(form.integrator, 'api_key')
        api_secret = IntegratorSetting.get_var(form.integrator, 'api_secret')
        success_url = IntegratorSetting.get_var(form.integrator, 'redirect_url_success')
        failed_url = IntegratorSetting.get_var(form.integrator, 'redirect_url_failed')
        jwt_endpoint = IntegratorSetting.get_var(form.integrator, 'jwt_endpoint')
        jwt_user = IntegratorSetting.get_var(form.integrator, 'jwt_user')
        jwt_pass = IntegratorSetting.get_var(form.integrator, 'jwt_pass')

        # Obtengo el JWT
        pd_jwt_gw = PagoDigitalJWTGateway(jwt_endpoint, jwt_user, jwt_pass)
        try:
            ret, content = pd_jwt_gw.doPost()
            if not ret:
                message = "%s - %s" % (content['STATUS_MESSAGE'], content['MESSAGE'])
                up.reply_error(message)
                context = {'redirect_url': failed_url}
                return render(request, template, context)
            if not 'TOKEN' in content:
                message = "JWT ERROR - TOKEN key not found"
                up.reply_error(message)
                context = {'redirect_url': failed_url}
                return render(request, template, context)
            pd_jwt = content['TOKEN']
        except Exception as e:
            message = 'jwt error: %s' % e
            up.reply_error(message)
            context = {'redirect_url': failed_url}
            return render(request, template, context)

        # Realizar add card y obtener token
        pd_ac_endpoint = IntegratorSetting.get_var(form.integrator, 'add_card_endpoint')
        pd_gw = PagoDigitalGateway(pd_ac_endpoint, api_key, api_secret, pd_jwt)
        pd_card = PagoDigitalCard(data['cc_number'], data['cc_cvv'], data['cc_fr_number'], data['cc_exp_month'],
                                  data['cc_exp_year'], data['name'], data['id_card'], data['address'], data['email'],
                                  data['phone'], data['city'], data['state'])
        try:
            ret, content = pd_gw.doPost(pd_card.to_dict())
            if not ret:
                message = "%s - %s" % (content['STATUS_MESSAGE'], content['MESSAGE'])
                up.reply_error(message)
                context = {'redirect_url': failed_url}
                return render(request, template, context)
            if 'CODIGO_RESPUESTA' in content:
                if str(content['CODIGO_RESPUESTA']) not in SUCCESS_CODES:
                    message = "ADD CARD ERROR - code: %s - message: %s" % (content['CODIGO_RESPUESTA'], content['RESPUESTA'])
                    up.reply_error(message)
                    context = {'redirect_url': failed_url}
                    return render(request, template, context)
            else:
                message = "ADD CARD ERROR - CODIGO_RESPUESTA not found"
                up.reply_error(message)
                context = {'redirect_url': failed_url}
                return render(request, template, context)
        except Exception as e:
            message = 'add card error: %s' % e
            up.reply_error(message)
            context = {'redirect_url': failed_url}
            return render(request, template, context)
        
        # Habilito tarjeta en UP
        up.enabled_card = True

        # Deshabilito cualquier tarjeta existente
        cards = Card.objects.filter(user=user, enabled=True)
        for card in cards:
            card.disable()
        
        # Creo la tarjeta o la obtengo si ya existe
        card = Card.get_by_token(up.user, content['TOKEN'])
        if card is not None:
            card.enable()
        else:
            card_exp = "%s/%s" % (data['cc_exp_month'], data['cc_exp_year'][-2:])
            card = Card.create_with_token(user, content['TOKEN'], data['cc_number'][-4:], card_exp, data['cc_fr_name'], form.integrator)
        
        # Verifico si es trial y aplico descuento si corresponde
        if up.is_trial:
            trial_flag = True
            disc_flag = False
            disc_pct = 0
        else:
            trial_flag = False 
            if up.has_discount:
                disc_flag = True
                disc_pct = up.disc_pct
            else:
                disc_pct = 0
                disc_flag = False

        # Genero tx id sumando al userid el timestamp
        payment_id = "PH_%s_%d" % (user.user_id, int(time()))

        # Creo el registro en PaymentHistory
        ph = PaymentHistory.create(up, payment_id, form.integrator, card, disc_pct)

        if ph.amount > 0:
            # Realizar pago
            pd_tx_endpoint = IntegratorSetting.get_var(form.integrator, 'process_tx_endpoint')
            pd_gw = PagoDigitalGateway(pd_tx_endpoint, api_key, api_secret, pd_jwt)
            try:
                pd_tx = PagoDigitalTx(int(ph.amount), card.token)
                ret, content = pd_gw.doPost(pd_tx.to_dict())
                print ret
                print content
            except Exception as e:
                message = 'Payment error: %s' % e
                up.reply_error(message)
                ph.error('', message)
                return False
        else:
            ret = True
            content = {'CODIGO_RESPUESTA':'-10', 'id':'-10', 'message': 'Pago con descuento del 100%'}
     
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
                    up.disc_counter -= 1
                if trial_flag:
                    up.trial_counter -= 1
            else:
                up.channel = 'R'
            up.save()            

            # Seteo los valores del PaymentHistory
            ph.status     = pr["ph_status"]
            ph.gateway_id = pr["ph_gatewayid"]
            ph.message    = pr["ph_message"]
            ph.save()

            if ph.status == 'A':
                redirect_url = success_url                
            else:
                redirect_url = failed_url

            if pr["user_expire"]:
                user.expire()

            # POST to promiscuus
            resp_promiscuus = post_to_promiscuus(ph, 'payment_commit')
            if resp_promiscuus['status'] == 'error':
                ph.message = "%s - Promiscuus error: %s" % (ph.message, resp_promiscuus['message'])
                ph.save()

            context = {'redirect_url': redirect_url}
            return render(request, template, context)
        
        else:
            message = "could not create user payment"
            up.reply_error(message)
            ph.error('', message)

            # POST to promiscuus
            resp_promiscuus = post_to_promiscuus(ph, 'payment_commit')
            if resp_promiscuus['status'] == 'error':
                ph.message = "%s - Promiscuus error: %s" % (ph.message, resp_promiscuus['message'])
                ph.save()

            context = {'redirect_url': failed_url}
            return render(request, template, context)

        
    ########  Metodo GET  ########    
    elif request.method == 'GET':
        user = User.get(request.GET['user_id'])
        template = Form.get_template(user, request.GET['token'])
        baseurl    = Setting.get_var('baseurl')

        if template is None:
            message = 'form not available'
            body = { 'status': 'error', 'message': message }
            return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)
        
        context = {'country': user.country.code, 'email': user.email, 'baseurl': baseurl}
        return render(request, template, context)
        
            
            
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                     Devuelve JSON con URL del formulario para agregar tarjeta                                 #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Parametros: user_id                                                                                        #
# Retorno: url                                                                                               #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@require_http_methods(["POST"])
def add_card_pagodigital(request):
    # Vars
    integrator = Integrator.get('pagodigital')
    baseurl    = Setting.get_var('baseurl')
    template   = 'pagodigital/pagodigital.html'

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
    keys = [ 'user_id' ]
    json_loader = __validate_json(data, keys)

    if json_loader['status'] == 'error':
        return HttpResponse(json.dumps(json_loader), content_type='application/json', status=http_BAD_REQUEST)

    # Verifico si el usuario existe y sino devuelvo error
    try:
        user       = User.objects.get(user_id=data['user_id'])
    except ObjectDoesNotExist:
        message = 'user does not exist'
        body = { 'status': 'error', 'message': message }
        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)

    # Obtengo el User Payment activo sino devuelvo error
    up = UserPayment.get_active(user)
    if up is None:
        message = 'enabled user payment does not exist'
        body = { 'status': 'error', 'message': message }
        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)
    
    # Creo el form
    form = Form.create(user, up, integrator, template, 'AC')
    if form is None:
        message = "form could not be created"
        body = { 'status': 'error', 'message': message }
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)        
        
    iframe_params = { 'user_id': user.user_id, 'token': form.token }
    iframe_url    = '%sapi/v1/pagodigital/addcard/form/?%s' % (baseurl, urlencode(iframe_params))
    body = { 'status': 'success', 'value': { 'url': iframe_url } }

    return HttpResponse(json.dumps(body), content_type="application/json", status=http_POST_OK)


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                               Form para agregar tarjeta                                    #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ---------- POST ---------                                                                                  #
# Parametros (POST JSON):                                                                                    # 
# ---------- GET ----------                                                                                  #
# Parametros: user_id, token                                                                                 #
# Retorno: redirect on error or success                                                                      #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@require_http_methods(["GET", "POST"])
def add_card_form_pagodigital(request):
    ########  Metodo POST  ########
    if request.method == 'POST':  
        data     = request.POST
        template = 'pagodigital/redirect.html'

        # Verifico las key mandatorias
        keys = [ 'name', 'phone', 'address', 'id_card', 'email', 'city', 
                 'state', 'cc_number', 'cc_exp_month', 'cc_exp_year', 
                 'cc_cvv', 'cc_fr_number', 'cc_fr_name', 'user_id' , 'token']
                
        json_loader = __validate_json(data, keys)
        if json_loader['status'] == 'error':
            return HttpResponse(json.dumps(json_loader), content_type='application/json', status=http_BAD_REQUEST)
        
        # Obtengo el usuario y el form vinculado al token
        user = User.get(data['user_id'])
        form = Form.get(user, data['token'])
        if form is None:
            message = 'form not available'
            body = { 'status': 'error', 'message': message }
            return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)

        # Obtengo settings del integrator
        api_key    = IntegratorSetting.get_var(form.integrator, 'api_key')
        api_secret = IntegratorSetting.get_var(form.integrator, 'api_secret')
        redirect_url = IntegratorSetting.get_var(form.integrator, 'redirect_url_add_card')
        jwt_endpoint = IntegratorSetting.get_var(form.integrator, 'jwt_endpoint')
        jwt_user = IntegratorSetting.get_var(form.integrator, 'jwt_user')
        jwt_pass = IntegratorSetting.get_var(form.integrator, 'jwt_pass')
        
        # Obtengo el JWT
        pd_jwt_gw = PagoDigitalJWTGateway(jwt_endpoint, jwt_user, jwt_pass)
        try:
            ret, content = pd_jwt_gw.doPost()
            if not ret:
                context = {'redirect_url': redirect_url}
                return render(request, template, context)
            if not 'TOKEN' in content:
                context = {'redirect_url': redirect_url}
                return render(request, template, context)
            pd_jwt = content['TOKEN']
        except Exception as e:
            context = {'redirect_url': redirect_url}
            return render(request, template, context)

        # Realizar add card y obtener token
        pd_ac_endpoint = IntegratorSetting.get_var(form.integrator, 'add_card_endpoint')
        pd_gw = PagoDigitalGateway(pd_ac_endpoint, api_key, api_secret, pd_jwt)
        pd_card = PagoDigitalCard(data['cc_number'], data['cc_cvv'], data['cc_fr_number'], data['cc_exp_month'],
                                  data['cc_exp_year'], data['name'], data['id_card'], data['address'], data['email'],
                                  data['phone'], data['city'], data['state'])
        try:
            ret, content = pd_gw.doPost(pd_card.to_dict())
            if not ret:
                context = {'redirect_url': redirect_url}
                return render(request, template, context)
            if 'CODIGO_RESPUESTA' in content:
                if str(content['CODIGO_RESPUESTA']) not in SUCCESS_CODES:
                    context = {'redirect_url': redirect_url}
                    return render(request, template, context)
            else:
                context = {'redirect_url': redirect_url}
                return render(request, template, context)
        except Exception as e:
            context = {'redirect_url': redirect_url}
            return render(request, template, context)
        
        # Deshabilito cualquier tarjeta existente
        cards = Card.objects.filter(user=user, enabled=True)
        for card in cards:
            card.disable()
        
        # Creo la tarjeta o la obtengo si ya existe
        card = Card.get_by_token(user, content['TOKEN'])
        if card is not None:
            card.enable()
        else:
            card_exp = "%s/%s" % (data['cc_exp_month'], data['cc_exp_year'][-2:])
            card = Card.create_with_token(user, content['TOKEN'], data['cc_number'][-4:], card_exp, data['cc_fr_name'], form.integrator)

        context = {'redirect_url': redirect_url}
        return render(request, template, context)


        ########  Metodo GET  ########    
    elif request.method == 'GET':
        user = User.get(request.GET['user_id'])
        template = Form.get_template(user, request.GET['token'])
        baseurl  = Setting.get_var('baseurl')

        if template is None:
            message = 'form not available'
            body = { 'status': 'error', 'message': message }
            return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)
        
        context = {'country': user.country.code, 'email': user.email, 'baseurl': baseurl}
        return render(request, template, context)


