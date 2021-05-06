# -*- coding: utf-8 -*-

from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt
from django.utils import timezone

import json
from time import time
from urllib import urlencode

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

from misc import prisma_translator
from misc import get_prisma_card_id
from misc import post_to_promiscuus

from prisma import PrismaGateway
from prisma import PrismaTx
from prisma import PrismaPaymentToken

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


def __check_apikey(request):
    if 'HTTP_X_AUTH_CCM_KEY' in request.META:
        if request.META['HTTP_X_AUTH_CCM_KEY'] == Setting.get_var('ma_apikey'):
            return {'status': 'success'}
        else:
            return {'status': 'error'}
    else:
        return {'status': 'error'}


def __validate_json(json_data, keys):
    for key in keys:
        if key not in json_data:
            message = "missing key in json: %s" % key
            return {'status': 'error', 'message': message}
        if json_data[key] is None or json_data[key] == '':
            message = "invalid value in key: %s" % key
            return {'status': 'error', 'message': message}
    return {'status': 'success'}



#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Devuelve JSON con URL de formulario de pago                                 #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Parametros:                                                                                                #
#     - Mandatorios: user_id, email, payment_date, recurrence                                                #
#     - Opcionales: discount, disc_counter                                                                   #
# Retorno: url                                                                                               #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@require_http_methods(["POST"])
def payment_prisma_view(request):
    # Vars
    integrator = Integrator.get('prisma')
    baseurl    = Setting.get_var('baseurl')
    template   = 'prisma/prisma.html'

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
    keys = [ 'user_id', 'email', 'payment_date','package_id']
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
    package = Package.get_by_id(data['package_id'], integrator)
            
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
    iframe_url    = '%sapi/v1/prisma/userpayment/form/?%s' % (baseurl, urlencode(iframe_params))
    body = { 'status': 'success', 'value': { 'url': iframe_url } }

    return HttpResponse(json.dumps(body), content_type="application/json", status=http_POST_OK)



#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Crea el UserPayment y realiza el addcard y pago                             #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ---------- GET ----------                                                                                  #
# Parametros: user_id, token                                                                                 #
# Retorno: url                                                                                               #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@xframe_options_exempt
@require_http_methods(["GET", "POST"])
def userpayment_form_prisma_view(request):
    ########  Metodo POST  ########
    if request.method == 'POST':  
        data = request.POST
        template = 'prisma/redirect.html'
        
        # Verifico las key mandatorias
        keys = [ 'card_number', 'card_expiration_month', 'card_expiration_year', 'security_code',
                 'card_holder_name', 'card_type', 'id_type', 'id_number', 'user_id', 'token']
        json_loader = __validate_json(data, keys)
        if json_loader['status'] == 'error':
            return HttpResponse(json.dumps(json_loader), content_type='application/json', status=http_BAD_REQUEST)
        
        # Obtengo el id de la tarjeta
        payment_method_id = get_prisma_card_id(data['card_type'])
        if payment_method_id is None:
            message = 'invalid payment method ID'
            body = { 'status': 'error', 'message': message }
            return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)

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
        public_apikey = IntegratorSetting.get_var(form.integrator, 'public_apikey')
        private_apikey = IntegratorSetting.get_var(form.integrator, 'private_apikey')
        success_url = IntegratorSetting.get_var(form.integrator, 'redirect_url_success')
        failed_url = IntegratorSetting.get_var(form.integrator, 'redirect_url_failed')
        endpoint = IntegratorSetting.get_var(form.integrator, 'endpoint')

        prisma_gw = PrismaGateway(endpoint, public_apikey, private_apikey)

        # Obtengo Token de pago
        prisma_token = PrismaPaymentToken(data['card_number'], data['card_expiration_month'], data['card_expiration_year'],
                                          data['security_code'], data['card_holder_name'], data['id_type'], data['id_number'])

        try:
            ret, content = prisma_gw.get_payment_token(prisma_token.serialize()) # Revisar que devuelve
            if not ret:
                up.reply_error(json.dumps(content))
                context = {'redirect_url': failed_url}
                return render(request, template, context)
            payment_token = content['id']
        except Exception as e:
            message = {'status': 'error', 'message': 'get_payment_token(): %s' % e}
            up.reply_error(json.dumps(message))
            context = {'redirect_url': failed_url}
            return render(request, template, context)


        # Realizo primer pago para tokenizar tarjeta
        payment_id = "PH_%s_%dc" % (user.user_id, int(time()))
        cc_bin = data['card_number'][:6]
        add_card_amount = 10 * 100
        add_card_tx = PrismaTx(user.user_id, user.email, payment_id, payment_token, cc_bin, add_card_amount, payment_method_id)
        try:
            ret, content = prisma_gw.add_card(add_card_tx.serialize())
            if not ret:
                up.reply_error(json.dumps(content))
                context = {'redirect_url': failed_url}
                return render(request, template, context)
            card_token = content['customer_token']
            if card_token is None:
                message = 'add card error - payment(): card token is null'
                up.reply_error(message)
                context = {'redirect_url': failed_url}
                return render(request, template, context)
        except Exception as e:
            message = 'add card error - payment(): %s' % e
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
        card = Card.get_by_token(up.user, card_token)
        if card is not None:
            card.enable()
        else:
            card_exp = "%s/%s" % (data['card_expiration_month'], data['card_expiration_month'])
            card = Card.create_with_token(user, card_token, data['card_number'][-4:], card_exp, data['card_type'], 
                                          form.integrator, data['security_code'], data['card_number'][:6])
        
        # Verifico si es un pago futuro
        if up.payment_date > timezone.now().date():
            context = {'redirect_url': success_url}
            return render(request, template, context)


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
            # Obtengo nuevo Token de pago
            payment_data = {'token': card.token, 'security_code': card.cvv} 
            try:
                ret, content = prisma_gw.get_recurrence_token(payment_data) # Revisar que devuelve
                if not ret:
                    up.reply_error(json.dumps(content))
                    context = {'redirect_url': failed_url}
                    return render(request, template, context)
                payment_token = content['id']
            except Exception as e:
                message = 'ERROR get_recurrence_token(): %s' % e
                up.reply_error(message)
                context = {'redirect_url': failed_url}
                return render(request, template, context)


            # Realizo pago
            final_amount = int(ph.amount*100) - add_card_amount
            prisma_tx = PrismaTx(user.user_id, user.email, payment_id, payment_token, cc_bin, final_amount, payment_method_id)
            try:
                ret, content = prisma_gw.payment(prisma_tx.serialize())
                if not ret:
                    up.reply_error(json.dumps(content))
                    context = {'redirect_url': failed_url}
                    return render(request, template, context)
                card_token = content['customer_token']
            except Exception as e:
                message = 'ERROR payment(): %s' % e
                up.reply_error(message)
                ph.error('', message)
                return False
        else:
            ret = True
            content = {'CODIGO_RESPUESTA':'-10', 'id':'-10', 'message': 'Pago con descuento del 100%'}            
     
        if ret:
            # Obtengo los valores segun la respuesta de Prisma
            pr = prisma_translator(content) 
           
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
            if ph.trial:
                ph.trial_duration = up.trial_recurrence
            else:
                ph.trial_duration = 0
            resp_promiscuus = post_to_promiscuus(ph, 'payment_commit')
            if resp_promiscuus['status'] == 'error':
                ph.message = "%s - Promiscuus error: %s" % (ph.message, resp_promiscuus['message'])
                ph.save()

            context = {'redirect_url': redirect_url}
            return render(request, template, context)
        
        else:
            message = json.dumps(content)
            up.reply_error(message)
            ph.error('', message)

            # POST to promiscuus
            if ph.trial:
                ph.trial_duration = up.trial_recurrence
            else:
                ph.trial_duration = 0
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
def add_card_prisma_view(request):
    # Vars
    integrator = Integrator.get('prisma')
    baseurl    = Setting.get_var('baseurl')
    template   = 'prisma/prisma.html'

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
        user = User.objects.get(user_id=data['user_id'])
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
    iframe_url    = '%sapi/v1/prisma/addcard/form/?%s' % (baseurl, urlencode(iframe_params))
    body = { 'status': 'success', 'value': { 'url': iframe_url } }

    return HttpResponse(json.dumps(body), content_type="application/json", status=http_POST_OK)



#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                               Form para agregar tarjeta                                    #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@require_http_methods(["POST"])
def add_card_form_prisma(request):
    data = request.POST
    template = 'prisma/redirect.html'
    
    # Verifico las key mandatorias
    keys = [ 'card_number', 'card_expiration_month', 'card_expiration_year', 
             'security_code', 'card_holder_name', 'card_type', 'user_id', 'token']
            
    json_loader = __validate_json(data, keys)
    if json_loader['status'] == 'error':
        return HttpResponse(json.dumps(json_loader), content_type='application/json', status=http_BAD_REQUEST)
    
    # Obtengo el id de la tarjeta
    payment_method_id = get_prisma_card_id(data['card_type'])
    if payment_method_id is None:
        context = {'redirect_url': redirect_url}
        return render(request, template, context)

    # Obtengo el usuario y el form vinculado al token
    user = User.get(data['user_id'])
    form = Form.get(user, data['token'])
    if form is None:
        context = {'redirect_url': redirect_url}
        return render(request, template, context)
    
    # Obtengo settings del integrator
    public_apikey = IntegratorSetting.get_var(form.integrator, 'public_apikey')
    private_apikey = IntegratorSetting.get_var(form.integrator, 'private_apikey')
    success_url = IntegratorSetting.get_var(form.integrator, 'redirect_url_success')
    failed_url = IntegratorSetting.get_var(form.integrator, 'redirect_url_failed')
    endpoint = IntegratorSetting.get_var(form.integrator, 'endpoint')

    prisma_gw = PrismaGateway(endpoint, public_apikey, private_apikey)

    # Obtengo Token de pago
    try:
        ret, content = prisma_gw.get_payment_token(data) # Revisar que devuelve
        if not ret:
            context = {'redirect_url': redirect_url}
            return render(request, template, context)
        payment_token = content['id']
    except Exception as e:
        context = {'redirect_url': redirect_url}
        return render(request, template, context)

    # Realizo pago para tokenizar tarjeta
    payment_id = "PH_%s_card_%d" % (user.user_id, int(time()))
    cc_bin = data['card_number'][:6]
    add_card_tx = PrismaTx(user.user_id, user.email, payment_id, payment_token, cc_bin, 1, payment_method_id)
    try:
        ret, content = prisma_gw.payment(add_card_tx.serialize())
        if not ret:
            context = {'redirect_url': redirect_url}
            return render(request, template, context)
        card_token = content['customer_token']
    except Exception as e:
        context = {'redirect_url': redirect_url}
        return render(request, template, context)

    # Deshabilito cualquier tarjeta existente
    cards = Card.objects.filter(user=user, enabled=True)
    for card in cards:
        card.disable()
    
    # Creo la tarjeta o la obtengo si ya existe
    card = Card.get_by_token(user, card_token)
    if card is not None:
        card.enable()
    else:
        card_exp = "%s/%s" % (data['card_expiration_month'], data['card_expiration_month'])
        card = Card.create_with_token(user, card_token, data['card_number'][-4:], card_exp, data['card_brand'], form.integrator, data['security_code'])

    context = {'redirect_url': redirect_url}
    return render(request, template, context)

    
