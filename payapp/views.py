#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Django 
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.core.exceptions import *

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
from time import mktime
from time import time

from paymentez import PaymentezGateway
from paymentez import PaymentezTx

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
        if int(json_data['recurrence']) <= 0:
            message = "invalid recurrence value"
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

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Creacion de nuevo pago recurrente                                                                  #
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# JSON - Mandatorios: user_id, email, country, token, card_number, card_exp, integrator, amount, currency, payment_date, recurrence #
# JSON - Opcionales: discount, disc_counter                                                                                         #
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@require_http_methods(["POST"])
def create_payment(request):
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
    keys = ['user_id', 'email', 'country', 'token', 'card_number', 'integrator', 'amount', 'currency', 'payment_date', 'recurrence']
    json_loader =  __validate_json(data, keys)
    if json_loader['status'] == 'error':
        return HttpResponse(json.dumps(json_loader), content_type="application/json", status=http_BAD_REQUEST)
    
    # Verifico que la currency exista
    try:
        currency = Currency.objects.get(code=data['currency'])
    except ObjectDoesNotExist:
        message = "currency %s does not exist" % data['currency']
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
    
    # Verifico que el pais exista
    try:
        country = Country.objects.get(code=data['country'])
    except ObjectDoesNotExist:
        message = "country %s does not exist" % data['country']
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    # Verifico que el integrador exista
    try:
        integrator = Integrator.objects.get(name=data['integrator'], country=country)
    except ObjectDoesNotExist:
        message = "integrator %s does not exist for country %s" % (data['integrator'], country.name)
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    # Verifico si el usuario existe y sino lo creo
    try:
        user = User.objects.get(user_id=data['user_id'])
    except ObjectDoesNotExist:
        user = User.create(data['user_id'], data['email'], country)
    
    # Si tiene algun UserPayment habilitado devuelvo un error
    try:
        up      = UserPayment.objects.get(user=user, enabled=True)
        message = "enabled user payment already exists" 
        body    = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
    except ObjectDoesNotExist:
        pass
    
    # Desabilito cualquier otra tarjeta del usuario
    try:
        card = Card.objects.get(user=user, enabled=True)
        card.disable()
    except ObjectDoesNotExist:
        pass
    
    # Creo la tarjeta si no existe con el metodo del integrador
    if integrator.method == 'TO':
        card = __get_card(user, data['token'])
        if card is not None:
            card.enable()
        else:
            # Creo la nueva tarjeta
            try:
                card = Card.create_with_token(user, data['token'], data['card_number'], data['card_exp'], integrator)
            except Exception:
                message = "new card could not be created"
                body    = {'status': 'error', 'message': message}
                return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)

    # Creo un nuevo pago recurrente.
    try:
        # Revisar si tiene o no descuento.
        payday = __payday_calc(data['payment_date'])
        if 'discount' in data and 'disc_counter' in data:
            up = UserPayment.create(user, 
                                    data['amount'], 
                                    currency, 
                                    data['payment_date'], 
                                    payday, 
                                    data['recurrence'],
                                    data['discount'],
                                    data['disc_counter'])
        else:
            up = UserPayment.create(user, 
                                    data['amount'], 
                                    currency, 
                                    data['payment_date'],
                                    payday, 
                                    data['recurrence'])
    except Exception as e:
        message = "could not create user payment: (%s)" % str(e)
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)
        
    
    # Realizar el pago
    if data['payment_date'] == 0 or data['payment_date'] == '0' or data['payment_date'] == 0.0:
        if integrator.name == 'paymentez':
            try:
                gw = PaymentezGateway(IntegratorSetting.get_var(integrator,'paymentez_server_application_code'),
                                      IntegratorSetting.get_var(integrator,'paymentez_server_app_key'),
                                      IntegratorSetting.get_var(integrator,'paymentez_endpoint'))
            except Exception as e:
                message = "could not create user payment: (%s)" % str(e)
                body = {'status': 'error', 'message': message}
                return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)

            # Aplico descuento si corresponde
            disc_flag = False
            if up.disc_counter > 0:
                disc_flag = True
                amount   = up.calculate_discount()
                disc_pct = up.disc_pct
            else:
                amount   = up.amount
                disc_pct = 0

            # Genero tx id sumando al userid el timestamp
            payment_id = "PH_%s_%d" % (user.user_id, int(time()))

            # Creo el registro en PaymentHistory
            ph = PaymentHistory.create(up, card, payment_id, amount, disc_pct)

            try:
                ret, content = gw.doPost(PaymentezTx(user.user_id,user.email,ph.amount,'HotGo',ph.payment_id,ph.taxable_amount,ph.vat_amount,card.token))
            except Excepcion as e:
                pass
                # Definir con SC que hacemos en caso de error de comunicacion al momento del pago. 
                # Se activa el UserPayment? Se activa la recurrencia? Que se le notifica al usuario?
                body = {'status': 'error', 'message': e}
                return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)

            if ret:
                # Fija la fecha de expiration del usuario
                user.add_to_expiration(int(data['recurrence']))
                # Lo pone activo
                up.status = 'AC'
                if disc_flag:
                    up.disc_counter = up.disc_counter - 1
                up.save()
                # Apruebo el Payment
                ph.approve(content['transaction']['id'])
            else:
                message = 'type: %s, help: %s, description: %s' % (content['error']['type'],content['error']['help'],content['error']['description'])
                up.reply_error(message)
                ph.error(message)
                body = {'status': 'error', 'message': message}
                return HttpResponse(json.dumps(body), content_type="application/json", status=http_UNPROCESSABLE_ENTITY)
        else:
            message = "could not create user payment: (Unknown Integrator: %s)" % str(integrator.name)
            body = {'status': 'error', 'message': message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)


    return HttpResponse(status=http_POST_OK)
    
    
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                Aplicar descuento para pago recurrente                                      #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# JSON - Mandatorios: user_id, discount, disc_counter                                                        #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++    
@require_http_methods(["POST"])
def payment_discount(request):
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
    keys = ['user_id', 'discount', 'disc_counter']
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
    
    # Obtengo el UserPayment y si no existe devulvo error
    try:
        up = UserPayment.objects.get(user=user, enabled=True)
    except ObjectDoesNotExist:
        message = "user_id %s has not enabled recurring payment" % data['user_id']
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)

    # Devuelvo error si existe algun descuento activo
    if up.disc_counter > 0:
        message = "discount already active"
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
        
    # Aplico el descuento
    try:
        up.discount(data['discount'], data['disc_counter'])
    except:
        message = "could not apply discount"
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)
    
    # Loguear en PaymentHistory
    
    return HttpResponse(status=http_POST_OK)
        
        
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
    try:
        up = UserPayment.objects.get(user=user, enabled=True)
    except ObjectDoesNotExist:
        message = "user_id %s has not enabled recurring payment" % data['user_id']
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
        
    # Cancelo la recurrencia
    try:
        up.cancel()
    except:
        message = "could not disable recurring payment"
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)
    
    # Loguear en PaymentHistory
    
    return HttpResponse(status=http_POST_OK)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                         Cambiar de tarjeta con token                                       #
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# JSON - Mandatorios: user_id, token, card_number, card_exp, integrator                                                             #
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
    keys = ['user_id', 'token', 'card_number', 'integrator']
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
        integrator = Integrator.objects.get(name=data['integrator'])
    except ObjectDoesNotExist:
        message = "integrator %s does not exist" % data['integrator']
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
        
    # Desabilito cualquier otra tarjeta del usuario
    try:
        card = Card.objects.get(user=user, enabled=True)
        card.disable()
    except ObjectDoesNotExist:
        pass

    # Verifico si la tarjeta ya fue cargada y la habilito.
    card = __get_card(user, data['token'])
    if card is not None:
        card.enable()
    else:
        # Creo la nueva tarjeta
        try:
            card = Card.create_with_token(user, data['token'], data['card_number'], data['card_exp'], integrator)
        except Exception:
            message = "new card could not be created"
            body = {'status': 'error', 'message': message}
            return HttpResponse(json.dumps(body), content_type="application/json", status=http_INTERNAL_ERROR)
    
    # Loguear en PaymentHistory la carga del nuevo pago recurrente
    
    return HttpResponse(status=http_POST_OK)

    
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
        ret['expiration'] = mktime(user.expiration.timetuple())
    except ObjectDoesNotExist:
        message = "user_id %s does not exist" % user_id
        body = {'status': 'error', 'message': message}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_BAD_REQUEST)
        
    # Obtengo el UserPayment activo y si no existe devuelvo solo fecha de expiracion
    try:
        up = UserPayment.objects.get(user=user, enabled=True)
    except ObjectDoesNotExist:
        ret['status'] = 'N'
        body = {'status': 'success', 'value': ret}
        return HttpResponse(json.dumps(body), content_type="application/json", status=http_REQUEST_OK)
    
    if up.status == 'ER':
        ret['status']   = 'E'
        ret['message']  = up.message
    else:
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
        
    cards = Card.objects.filter(user=user)
    value = []
    for card in cards:
        ret = {}
        ret['token']      = card.token
        ret['number']     = card.number
        ret['name']       = card.name
        ret['expiration'] = card.expiration
        ret['cvc']        = card.cvc
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
        card = Card.objects.get(user=user, enabled=True)
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
    ret['integrator'] = card.integrator.name
    ret['enabled']    = card.enabled
        
    body = {'status': 'success', 'value': ret}
    return HttpResponse(json.dumps(body), content_type="application/json", status=http_REQUEST_OK)
