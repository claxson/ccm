# -*- coding: utf-8 -*-

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Django 
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist


#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# App Models
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from models import User
from models import UserPayment
from models import Setting
from models import Card
from models import PaymentHistory
from models import Currency
from models import Integrator
from models import Country
from models import IntegratorSetting

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Misc
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
import json
from datetime import datetime
from datetime import date
from time import mktime
from time import time

from paymentez import PaymentezGateway
from paymentez import PaymentezTx
from paymentez import PaymentezRefund
from paymentez import DeleteCard

from misc import paymentez_translator
from misc import paymentez_intercom_metadata
from misc import post_to_promiscuus

from intercom import Intercom

from commercegate_views import cancel_commercegate

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


# Create your views here.

def __validate_json(json_data, keys):
    for key in keys:
        if key not in json_data:
            message = "missing key in json: %s" % key
            return {'status': 'error', 'message': message}
    if 'discount' in json_data:
        if int(json_data['discount']) < 1 or int(json_data['discount']) > 100:
            message = "invalid discount percentage"
            return {'status': 'error', 'message': message}
    if 'disc_counter' in json_data:
        if int(json_data['disc_counter']) <= 0:
            message = "invalid disc_counter value"
            return {'status': 'error', 'message': message}
    if 'amount' in json_data:
        if float(json_data['amount']) <= 0:
            message = "invalid amount value"
            return {'status': 'error', 'message': message}
    if 'recurrence' in json_data:
        t, r = divmod(int(json_data['recurrence']), 30)
        if t < 1 or r > 0:
            message = "invalid recurrence value. value %s is not multiple of 30 " % str(json_data['recurrence'])
            return {'status': 'error', 'message': message}
    
    return {'status': 'success'}

def __payday_calc(payment_date):
    if payment_date == 0 or payment_date == 0.0 or payment_date == "0":
        payment_date = time()
    day = datetime.fromtimestamp(int(payment_date)).strftime('%d')
    if int(day) > 28:
        return 28
    else:
        return int(day)

def __check_apikey(request):
    if 'HTTP_X_AUTH_CCM_KEY' in request.META:
        if request.META['HTTP_X_AUTH_CCM_KEY'] == Setting.get_var('ma_apikey'):
            return {'status': 'success'}
        else:
            return {'status': 'error'}
    else:
        return {'status': 'error'}


def __get_card(user, token):
    try:
        card = Card.objects.get(user=user, token=token)
        return card
    except:
        return None

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Creacion de nuevo pago recurrente                      #
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# JSON - Mandatorios: user_id, email, country, token, card_number, card_exp, card_type, #
#                     integrator, amount, currency, payment_date, recurrence            #
# JSON - Opcionales: discount, disc_counter                                             #
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@require_http_methods(["POST"])
def create_payment(request):
    # Verifico ApiKey
    cap = __check_apikey(request)
    if cap['status'] == 'error':
        return HttpResponse(status=http_UNAUTHORIZED)
        
    # Cargo el json
    try:
        data = json.loads(request.body)
        print "CONTENT MA: %s" % data
    except Exception:
        user_message = "Ocurrió un error con el pago, por favor reintente nuevamente más tarde"
        message = "error decoding json"
        body = {'status': 'error', 'message': message, "user_message": user_message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
    
    # Verifico las key mandatorios del json    
    keys = ['user_id', 'email', 'country', 'token', 'card_number', 'card_exp','card_type',
            'integrator', 'amount', 'currency', 'payment_date', 'recurrence']
    json_loader = __validate_json(data, keys)
    if json_loader['status'] == 'error':
        json_loader['user_message'] = "Ocurrió un error con el pago, por favor reintente nuevamente más tarde"
        return HttpResponse(json.dumps(json_loader), content_type="application/json", status=http_BAD_REQUEST)
    
    # Verifico que la currency exista
    try:
        currency = Currency.objects.get(code=data['currency'].lower())
    except ObjectDoesNotExist:
        user_message = "Ocurrió un error con el pago, por favor reintente nuevamente más tarde"
        message = "currency %s does not exist" % data['currency']
        body = {'status': 'error', 'message': message, 'user_message': user_message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
    
    # Verifico que el pais exista
    try:
        country = Country.objects.get(code=data['country'].lower())
    except ObjectDoesNotExist:
        user_message = "Ocurrió un error con el pago, por favor reintente nuevamente más tarde"
        message = "country %s does not exist" % data['country']
        body = {'status': 'error', 'message': message, 'user_message': user_message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    # Verifico que el integrador exista
    try:
        integrator = Integrator.objects.get(name=data['integrator'], country=country)
    except ObjectDoesNotExist:
        user_message = "Ocurrió un error con el pago, por favor reintente nuevamente más tarde"
        message = "integrator %s does not exist for country %s" % (data['integrator'], country.name)
        body = {'status': 'error', 'message': message, 'user_message': user_message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    # Verifico si el usuario existe y sino lo creo
    try:
        user       = User.objects.get(user_id=data['user_id'])
        user.email = data['email']
        user.save()
    except ObjectDoesNotExist:
        user = User.create(data['user_id'], data['email'], country)
    
    # Si tiene algun UserPayment habilitado devuelvo un error
    if UserPayment.objects.filter(user=user, enabled=True).exists():
        user_message = "Ocurrió un error con el pago, por favor reintente nuevamente más tarde"
        message = "enabled user payment already exists" 
        body    = {'status': 'error', 'message': message, 'user_message': user_message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
    
    # Desabilito cualquier otra tarjeta del usuario
    cards = Card.objects.filter(user=user, enabled=True)
    for card in cards:
        card.disable()

    
    # Creo la tarjeta si no existe con el metodo del integrador
    if integrator.method == 'TO':
        card = __get_card(user, data['token'])
        if card is not None:
            card.enable()
        else:
            # Creo la nueva tarjeta
            try:
                card = Card.create_with_token(user, data['token'], data['card_number'],
                                              data['card_exp'], data['card_type'], integrator)
            except Exception:
                user_message = "Ocurrió un error con el pago, por favor reintente nuevamente más tarde"
                message = "new card could not be created"
                body    = {'status': 'error', 'message': message, 'user_message': user_message}
                return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)
    else:
        user_message = "Ocurrió un error con el pago, por favor reintente nuevamente más tarde"
        message = "integrator %s unknown" % integrator.method
        body = {'status': 'error', 'message': message, 'user_message': user_message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)

    # Creo un nuevo pago recurrente.
    try:
        # Revisar si tiene o no descuento.
        payday = __payday_calc(data['payment_date'])
        if 'discount' in data and 'disc_counter' in data:
            up = UserPayment.create(user, 
                                    data['recurrence'],
                                    data['amount'],
                                    currency,
                                    data['payment_date'],
                                    payday,
                                    data['discount'],
                                    data['disc_counter'],
                                    True)
        else:
            up = UserPayment.create(user,
                                    data['recurrence'],
                                    data['amount'],
                                    currency,
                                    data['payment_date'],
                                    payday,
                                    0,
                                    0,
                                    True)
    except Exception as e:
        user_message = "Ocurrió un error con el pago, por favor reintente nuevamente más tarde"
        message = "could not create user payment: (%s)" % str(e)
        body = {'status': 'error', 'message': message, 'user_message': user_message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)
        
    
    # Realizar el pago
    if data['payment_date'] == 0 or data['payment_date'] == '0' or data['payment_date'] == 0.0:
        if integrator.name == 'paymentez':
            try:
                gw = PaymentezGateway(IntegratorSetting.get_var(integrator,'paymentez_server_application_code'),
                                      IntegratorSetting.get_var(integrator,'paymentez_server_app_key'),
                                      IntegratorSetting.get_var(integrator,'paymentez_endpoint'))
            except Exception as e:
                user_message = "Ocurrió un error con el pago, por favor reintente nuevamente más tarde"
                message = "could not create user payment: (%s)" % str(e)
                body = {'status': 'error', 'message': message, 'user_message': user_message}
                return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)

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
            ph = PaymentHistory.create(up, payment_id, integrator, card, disc_pct)

            if ph.amount > 0:
                try:
                    ret, content = gw.doPost(PaymentezTx(user.user_id, user.email, ph.amount,'HotGo', ph.payment_id
                                                         , ph.taxable_amount, ph.vat_amount, card.token))
                    print "CONTENT: %s" % str(content)
                except Exception:
                    # Pongo el pago en Waiting Callback
                    ph.status = "W"
                    ph.save()
                    user_message = "Ocurrió un error en la comunicación. Recibirás un correo electrónico en breve con " \
                                   "los detalles de tu transacción. Por cualquier duda, contáctate con soporte@hotgo.tv"
                    message = "communication error with paymentez, waiting callback"
                    body = {'status': 'error', 'message': message, 'user_message': user_message}
                    return HttpResponse(json.dumps(body), content_type="application/json", status=http_PAYMENT_REQUIRED)
            else:
                ret = True
                content = {'transaction': {'status_detail':'-10', 'id':'-10', 'message':'Pago con descuento del 100%'}}
                pr  = paymentez_translator(content)

            if ret:
                # Obtengo los valores segun la respuesta de Paymentez
                pr = paymentez_translator(content)
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

                if pr["intercom"]["action"]:
                    ep    = Setting.get_var('intercom_endpoint')
                    token = Setting.get_var('intercom_token')
                    if user.expiration is not None:
                        content['transaction']['expire_at'] = mktime(user.expiration.timetuple())
                    try:
                        intercom = Intercom(ep, token)
                        reply = intercom.submitEvent(up.user.user_id, up.user.email, pr["intercom"]["event"],
                                                     paymentez_intercom_metadata(content['transaction']))
                        if not reply:
                            ph.message = "%s - Intercom error: cannot post the event" % (ph.message)
                            ph.save()
                    except Exception as e:
                        ph.message = "%s - Intercom error: %s" % (ph.message, str(e))
                        ph.save()                
                
                # POST to promiscuus
                resp_promiscuus = post_to_promiscuus(ph, 'payment_commit')
                if resp_promiscuus['status'] == 'error':
                    ph.message = "%s - Promiscuus error: %s" % (ph.message, resp_promiscuus['message'])
                    ph.save()

                body = {'status': rep_status, 'message': '', 'user_message': pr['user_message']}
                return HttpResponse(json.dumps(body), content_type="application/json", status=http_POST_OK)

            else:
                message = 'type: %s, help: %s, description: %s' % (content['error']['type'],
                                                                   content['error']['help'],
                                                                   content['error']['description'])
                up.reply_error(message)
                ph.error('', content)
                user_message = "Ocurrió un error con el pago, por favor reintente nuevamente más tarde"

                # POST to promiscuus
                resp_promiscuus = post_to_promiscuus(ph, 'payment_commit')
                if resp_promiscuus['status'] == 'error':
                    ph.message = "%s - Promiscuus error: %s" % (ph.message, resp_promiscuus['message'])
                    ph.save()

                body = {'status': 'error', 'message': message, 'user_message': user_message}
                return HttpResponse(json.dumps(body), content_type="application/json", status=http_UNPROCESSABLE_ENTITY)

        else:
            user_message = "Ocurrió un error con el pago, por favor reintente nuevamente más tarde"
            message = "could not create user payment: (Unknown Integrator: %s)" % str(integrator.name)
            body = {'status': 'error', 'message': message, 'user_message': user_message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)

    user_message = "Suscripción exitosa"
    body = {'status': 'success', 'message': '', 'user_message': user_message}
    return HttpResponse(json.dumps(body), content_type="application/json", status=http_POST_OK)
    
    
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Aplicar descuento para pago recurrente                                      #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# JSON - Mandatorios: user_id, discount, disc_counter                                                        #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++    
@require_http_methods(["GET", "POST"])
def payment_discount(request):
   # Verifico ApiKey
    cap = __check_apikey(request)
    if cap['status'] == 'error':
        return HttpResponse(status=http_UNAUTHORIZED)
    
    if request.method == 'POST':
        # Cargo el json
        try:
            data = json.loads(request.body)
        except Exception:
            message = "error decoding json"
            body = {'status': 'error', 'message': message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
    
        # Verifico las key mandatorios del json    
        keys = ['user_id', 'discount', 'disc_counter']
        json_loader =  __validate_json(data, keys)
        if json_loader['status'] == 'error':
            return HttpResponse(json.dumps(json_loader), content_type="application/json", status=http_BAD_REQUEST)
        
        user_id  = data['user_id']
        discount = data['discount']
        disc_counter = data['disc_counter']
        status = http_POST_OK
        
    else:
        try: 
            user_id = request.GET['user_id']
            discount = int(request.GET['discount'])
            disc_counter = int(request.GET['disc_counter'])
            status = http_REQUEST_OK
        except:
            message = "missing parameter"
            body = {'status': 'error', 'message': message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)        
        
        if discount < 1 or discount > 100 or disc_counter < 1:
            message = "invalid parameter value"
            body = {'status': 'error', 'message': message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
        
    # Verifico que el usuario exista
    try:
        user = User.objects.get(user_id=user_id)
    except ObjectDoesNotExist:
        message = "user_id %s does not exist" % user_id
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
    
    # Obtengo el UserPayment y si no existe devulvo error
    up = UserPayment.get_active(user=user)
    if up is None:
        message = "user_id %s has not enabled recurring payment" % user_id
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    """    
    # Devuelvo error si existe algun descuento activo
    if up.disc_counter > 0:
        message = "discount already active"
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
    """
    
    # Aplico el descuento
    try:
        up.discount(discount, disc_counter)
    except:
        message = "could not apply discount"
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)
    
    return HttpResponse(status=status)
        
        
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                         Cancelar pago recurrente                                           #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# JSON - Mandatorios: user_id                                                                                #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++        
@require_http_methods(["POST"])
def cancel_payment(request):
    # Verifico ApiKey
    cap = __check_apikey(request)
    if cap['status'] == 'error':
        return HttpResponse(status=http_UNAUTHORIZED)
        
    # Cargo el json
    try:
        data = json.loads(request.body)
    except Exception:
        message = "error decoding json"
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
    
    # Verifico las key mandatorios del json    
    keys = ['user_id']
    json_loader =  __validate_json(data, keys)
    if json_loader['status'] == 'error':
        return HttpResponse(json.dumps(json_loader), content_type="application/json", status=http_BAD_REQUEST)
        
    # Verifico que el usuario exista
    try:
        user = User.objects.get(user_id=data['user_id'])
    except ObjectDoesNotExist:
        message = "user_id %s does not exist" % data['user_id']
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
        
    # Obtengo el UserPayment activo y si no existe devulvo error
    up = UserPayment.get_active(user=user)
    if up is None:
        message = "user_id %s has not enabled recurring payment" % data['user_id']
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
    
    # Si el integrador es CommerceGate ejecuto baja para ese integrador
    ph = PaymentHistory.objects.filter(user_payment=up).order_by('-id')[0]
    if ph.integrator.name == 'commerce_gate':
        return cancel_commercegate(request)
        

    # Cancelo la recurrencia
    try:
        up.user_cancel()
    except:
        message = "could not disable recurring payment"
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)

    # Envio envento a intercom
    ep    = Setting.get_var('intercom_endpoint')
    token = Setting.get_var('intercom_token')
    try:
        intercom = Intercom(ep, token)
        reply = intercom.submitEvent(up.user.user_id, up.user.email, "cancelled-sub",
                                     {"event_description": "recurrencia cancelada por el usuario"})
        if not reply:
            up.message = "Intercom error: cannot post the event"
            up.save()
    except Exception as e:
        up.message = "Intercom error: %s" % str(e)
        up.save()
    
    # POST to promiscuus
    resp_promiscuus = post_to_promiscuus(up, 'cancel')
    if resp_promiscuus['status'] == 'error':
        up.message = "%s - Promiscuus error: %s" % (up.message, resp_promiscuus['message'])
        up.save()

    return HttpResponse(status=http_POST_OK)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                         Cambiar de tarjeta con token                                       #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# JSON - Mandatorios: user_id, token, card_number, card_exp, card_type, integrator                           #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ 
@require_http_methods(["POST"])
def change_token_card(request):
    # Verifico ApiKey
    cap = __check_apikey(request)
    if cap['status'] == 'error':
        return HttpResponse(status=http_UNAUTHORIZED)
        
    # Cargo el json
    try:
        data = json.loads(request.body)
    except Exception:
        message = "error decoding json"
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
    
    # Verifico las key mandatorios del json    
    keys = ['user_id', 'token', 'card_number', 'card_type', 'integrator']
    json_loader =  __validate_json(data, keys)
    if json_loader['status'] == 'error':
        return HttpResponse(json.dumps(json_loader), content_type="application/json", status=http_BAD_REQUEST)
        
    # Verifico que el usuario exista
    try:
        user = User.objects.get(user_id=data['user_id'])
    except ObjectDoesNotExist:
        message = "user_id %s does not exist" % data['user_id']
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
        
    # Verifico que el integrador exista
    try:
        integrator = Integrator.objects.get(name=data['integrator'], country=user.country)
    except ObjectDoesNotExist:
        message = "integrator %s does not exist" % data['integrator']
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    # Desabilito cualquier otra tarjeta del usuario
    cards = Card.objects.filter(user=user, enabled=True)
    for card in cards:
        card.disable()

    # Verifico si la tarjeta ya fue cargada y la habilito.
    card = __get_card(user, data['token'])
    if card is not None:
        card.enable()
    else:
        # Creo la nueva tarjeta
        try:
            card = Card.create_with_token(user, data['token'], data['card_number'],
                                          data['card_exp'], data['card_type'], integrator)
        except Exception:
            message = "new card could not be created"
            body = {'status': 'error', 'message': message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)

    
    return HttpResponse(status=http_POST_OK)


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                         Modificar email del usuario                                        #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# JSON - Mandatorios: user_id, email                                                                         #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@require_http_methods(["POST"])
def change_user_email(request):
    # Verifico ApiKey
    cap = __check_apikey(request)
    if cap['status'] == 'error':
        return HttpResponse(status=http_UNAUTHORIZED)

    # Cargo el json
    try:
        data = json.loads(request.body)
    except Exception:
        message = "error decoding json"
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    # Verifico las key mandatorios del json
    keys = ['user_id', 'email']
    json_loader = __validate_json(data, keys)
    if json_loader['status'] == 'error':
        return HttpResponse(json.dumps(json_loader), content_type="application/json", status=http_BAD_REQUEST)

    # Verifico que el usuario exista
    try:
        user = User.objects.get(user_id=data['user_id'])
    except ObjectDoesNotExist:
        message = "user_id %s does not exist" % data['user_id']
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    user.email = data['email']
    user.save()

    return HttpResponse(status=http_POST_OK)


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                        Eliminar tarjeta no activa                                          #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# JSON - Mandatorios: token                                                                                  #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@require_http_methods(["GET"])
def delete_card(request, token):
    # Verifico ApiKey
    cap = __check_apikey(request)
    if cap['status'] == 'error':
        return HttpResponse(status=http_UNAUTHORIZED)

    try:
        card = Card.objects.get(token=token)
    except ObjectDoesNotExist:
        message = "token %s does not exist" % token
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    if card.enabled:
        message = "card with token %s cannot be deleted because is enabled" % str(token)
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    if card.integrator.name == 'paymentez':
        try:
            gw = PaymentezGateway(IntegratorSetting.get_var(card.integrator, 'paymentez_server_application_code'),
                                  IntegratorSetting.get_var(card.integrator, 'paymentez_server_app_key'),
                                  IntegratorSetting.get_var(card.integrator, 'paymentez_deletecard_endpoint'))
        except Exception as e:
            message = "could not delete the card: (%s)" % str(e)
            body = {'status': 'error', 'message': message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)

        try:
            ret, content = gw.doPost(DeleteCard(card.token, card.user.user_id))
        except Exception as e:
            message = "could not delete the card: (%s)" % str(e)
            body = {'status': 'error', 'message': message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)

        if ret:
            card.sdelete()
            message = "card with token %s deleted succesfully" % str(card.token)
            body = {'status': 'success', 'message': message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_REQUEST_OK)
        else:
            message = 'type: %s, help: %s, description: %s' % (content['error']['type'],
                                                               content['error']['help'],
                                                               content['error']['description'])
            body = {'status': 'error', 'message': message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_UNPROCESSABLE_ENTITY)
    
    else:
        card.sdelete()
        message = "card with token %s deleted succesfully" % str(card.token)
        body = {'status': 'success', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_REQUEST_OK)


    
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                        Devuelve JSON con el estado de la suscripcion del usuario                           #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Parametros: user_id                                                                                        #
# Retorno: JSON: status, expiration, recurrence, payment_date, currency, amount, discount, disc_counter      #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ 
@require_http_methods(["GET"])
def user_status(request, user_id):
    ret = {}
    # Verifico ApiKey
    cap = __check_apikey(request)
    if cap['status'] == 'error':
        return HttpResponse(status=http_UNAUTHORIZED)

    # Verifico que el usuario exista
    try:
        user = User.objects.get(user_id=user_id)
    except ObjectDoesNotExist:
        message = "user_id %s does not exist" % user_id
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    if user.expiration is not None and user.expiration >= date.today():
        # A la expiracion le sumo un dia para evitar dejarlo sin acceso sin haber intentado cobrarle
        ret['expiration'] = mktime(user.expiration.timetuple())
    else:
        ret['expiration'] = None

    # Obtengo el UserPayment activo y si no existe devuelvo solo fecha de expiracion
    try:
        up = UserPayment.objects.get(user=user, status='AC')
    except ObjectDoesNotExist:
        ret['status']  = 'E'
        ret['message'] = 'Enabled UserPayement not found'
        body = {'status': 'success', 'value': ret}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_REQUEST_OK)
    
    ret['status']   = 'A'
    ret['message']  = ''
 
    ret['recurrence']   = up.recurrence
    ret['payment_date'] = mktime(up.payment_date.timetuple())
    ret['currency']     = up.currency.code
    ret['amount']       = up.amount
    ret['discount']     = up.disc_pct
    ret['disc_counter'] = up.disc_counter
    
    body = {'status': 'success', 'value': ret}
    return HttpResponse(json.dumps(body), content_type="application/json", status=http_REQUEST_OK)
    

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Devuelve JSON con listado de tarjetas del usuario                           #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Parametros: user_id                                                                                        #
# Retorno: Listado de tarjeas                                                                                #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@require_http_methods(["GET"])
def get_cards(request, user_id):
    # Verifico ApiKey
    cap = __check_apikey(request)
    if cap['status'] == 'error':
        return HttpResponse(status=http_UNAUTHORIZED)

    # Verifico que el usuario exista
    try:
        user = User.objects.get(user_id=user_id)
    except ObjectDoesNotExist:
        message = "user_id %s does not exist" % user_id
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
        
    cards = Card.objects.filter(user=user, deleted=False)
    value = []
    for card in cards:
        ret = {}
        ret['token']      = card.token
        ret['number']     = card.number
        ret['name']       = card.name
        ret['expiration'] = card.expiration
        ret['cvc']        = card.cvc
        ret['card_type']  = card.card_type
        ret['integrator'] = card.integrator.name
        ret['enabled']    = card.enabled
        value.append(ret)
        
    body = {'status': 'success', 'value': value}
    return HttpResponse(json.dumps(body), content_type="application/json", status=http_REQUEST_OK)


 
        
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Devuelve JSON con la tarjeta activa del usuario                             #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Parametros: user_id                                                                                        #
# Retorno: Listado de tarjeas                                                                                #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++        
@require_http_methods(["GET"])
def get_enabled_card(request, user_id):
    # Verifico ApiKey
    cap = __check_apikey(request)
    if cap['status'] == 'error':
        return HttpResponse(status=http_UNAUTHORIZED)

    # Verifico que el usuario exista
    try:
        user = User.objects.get(user_id=user_id)
    except ObjectDoesNotExist:
        message = "user_id %s does not exist" % user_id
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
        
    try:    
        card = Card.objects.get(user=user, enabled=True, deleted=False)
    except ObjectDoesNotExist:
        message = "card enabled not found"
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
    
    ret = {}
    ret['token']      = card.token
    ret['number']     = card.number
    ret['name']       = card.name
    ret['expiration'] = card.expiration
    ret['cvc']        = card.cvc
    ret['card_type']  = card.card_type
    ret['integrator'] = card.integrator.name
    ret['enabled']    = card.enabled
        
    body = {'status': 'success', 'value': ret}
    return HttpResponse(json.dumps(body), content_type="application/json", status=http_REQUEST_OK)


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Realiza un refund para el PaymentHistory indicado                           #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Parametros: payment_history id (payment_id)                                                                #
# Retorno: estado del refund                                                                                 #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@require_http_methods(["GET"])
def refund(request, payment_id):
    # Verifico ApiKey
    cap = __check_apikey(request)
    if cap['status'] == 'error':
        return HttpResponse(status=http_UNAUTHORIZED)

    # Verifico que el Payment exista
    try:
        ph = PaymentHistory.objects.get(payment_id=payment_id)
    except ObjectDoesNotExist:
        message = "paymentd_id not found"
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    if ph.integrator.name == 'paymentez':
        try:
            gw = PaymentezGateway(IntegratorSetting.get_var(ph.integrator, 'paymentez_server_application_code'),
                                  IntegratorSetting.get_var(ph.integrator, 'paymentez_server_app_key'),
                                  IntegratorSetting.get_var(ph.integrator, 'paymentez_refund_endpoint'))
        except Exception as e:
            message = "could not create user payment: (%s)" % str(e)
            body = {'status': 'error', 'message': message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)

        try:
            ret, content = gw.doPost(PaymentezRefund(ph.gateway_id))
        except Exception:
            message = "communication error"
            body = {'status': 'error', 'message': message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_PAYMENT_REQUIRED)

        if ret:
            if content['status'] == 'success':
                ph.cancel(ph.gateway_id, 'claxson refund')
                ph.user_payment.cancel("F", 'claxson refund')
                return HttpResponse(json.dumps(content), content_type="application/json", status=http_REQUEST_OK)
            else:
                message = str(content['detail'])
                body = {'status': 'error', 'message': message}
                return HttpResponse(json.dumps(body), content_type="application/json", status=http_UNPROCESSABLE_ENTITY)
        else:
            message = str(content)
            body = {'status': 'error', 'message': message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_UNPROCESSABLE_ENTITY)

    else:
        message = "could not create user payment: (Unknown Integrator: %s)" % str(ph.integrator.name)
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)
