
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Django
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.core.exceptions import *
from django.utils import timezone
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
import hashlib
from datetime import datetime
from time import mktime
from time import time

from misc import paymentez_translator
#from misc import paymentez_intercom_metadata
from misc import post_to_promiscuus

#from intercom import Intercom

import logging
import urllib
import xmltodict

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


def __validate_json(json_data, keys):
    for item in keys:
        for key, value in item.iteritems():
            if key in json_data:
                for v in value:
                    if v not in json_data[key]:
                        message = "missing key in json: %s" % v
                        return {'status': 'error', 'message': message}
            else:
                message = "missing key in json: %s" % key
                return {'status': 'error', 'message': message}

    return {'status': 'success'}


def __validate_stoken(data, country):
    country    = Country.objects.get(code=country)
    integrator = Integrator.objects.get(name="paymentez", country=country)
    tx_id    = data["transaction"]["id"]
    app_code = data["transaction"]["application_code"]
    stoken   = data["transaction"]["stoken"]
    user_id  = data["user"]["id"]
    app_key  = IntegratorSetting.get_var(integrator, 'paymentez_server_app_key')

    string = "%s_%s_%s_%s" % (tx_id, app_code, user_id, app_key)
    
    if stoken.lower() == hashlib.md5(string).hexdigest():
        return True
    else:
        return False


def __callback_paymentez_proc(data, country):
    # Verifico el stoken
    if not __validate_stoken(data, country):
        body = {"status": "error", "message": "not authorized"}
        return HttpResponse(json.dumps(body), content_type="application/json", status=200)

    # Obtengo los valores segun la respuesta de Paymentez
    pr = paymentez_translator(data)

    # Obtengo el PaymentHistory con el dev_reference informado
    try:
        ph = PaymentHistory.objects.get(payment_id=data["transaction"]["dev_reference"])
    except ObjectDoesNotExist:
        body = {"status": "error", "message": "invalid dev_refence"}
        return HttpResponse(json.dumps(body), content_type="application/json", status=200)

    # Verifico que este en Waiting Callback
    if ph.status == 'W' or (ph.status == 'A' and pr["ph_status"] == 'C'):

        # Seteo los valores de la UserPayment
        ph.user_payment.status  = pr["up_status"]
        ph.user_payment.message = pr["up_message"]
        ph.user_payment.enabled = pr["up_recurrence"]

        if ph.user_payment.status == 'AC':
            # calcular next_payment_day
            ph.user_payment.payment_date = ph.user_payment.calc_payment_date()
            # Fija la fecha de expiration del usuario
            ph.user_payment.user.set_expiration(ph.user_payment.payment_date)
            # Si es trial, resto uno al contador
            if ph.trial:
                ph.user_payment.trial_counter -= 1
            else:
                # Si tiene descuento, resto uno al contador
                if ph.user_payment.has_discount:
                    ph.user_payment.disc_counter -= 1
            
        else:
            ph.user_payment.channel = 'C'
        ph.user_payment.save()

        # Seteo los valores del PaymentHistory
        ph.status     = pr["ph_status"]
        ph.gateway_id = pr["ph_gatewayid"]
        ph.message    = pr["ph_message"]
        ph.save()

        if pr["user_expire"]:
            ph.user_payment.user.expire()

        # Verico si es primer pago o rebill        
        if PaymentHistory.objects.filter(user_payment=ph.user_payment).count() == 1:
            promiscuus_event = 'payment_commit'            
        else:
            promiscuus_event = 'rebill'

        # POST to promiscuus
        if ph.user_payment.status == 'AC':
            resp_promiscuus = post_to_promiscuus(ph, promiscuus_event)
            if resp_promiscuus['status'] == 'error':
                ph.message = "%s - Promiscuus error: %s" % (ph.message, resp_promiscuus['message'])
                ph.save()
        elif ph.user_payment.status == 'CA':
            resp_promiscuus = post_to_promiscuus(ph.user_payment, 'cancel')
            if resp_promiscuus['status'] == 'error':
                ph.user_payment.message = "%s - Promiscuus error: %s" % (ph.user_payment.message, resp_promiscuus['message'])
                ph.user_payment.save()

    else:
        body = {"status": "error", "message": "ignoring callback: PH status %s" % ph.status}
        return HttpResponse(json.dumps(body), content_type="application/json", status=200)

    

    body = {'status': 'success', 'message': ''}
    return HttpResponse(json.dumps(body), content_type="application/json", status=200)


@require_http_methods(["POST"])
def callback_paymentez(request):
    # Cargo el json
    try:
        data = json.loads(request.body)
    except Exception:
        body = {"status": "error", "message": "error loading json"}
        return HttpResponse(json.dumps(body), content_type="application/json", status=200)

    # Verifico las key mandatorios del json
    keys = [{'transaction': ['id', 'application_code', 'dev_reference', 'stoken']}, {'user':['id']}]
    json_loader = __validate_json(data, keys)
    if json_loader['status'] == 'error':
        return HttpResponse(json.dumps(json_loader), content_type="application/json", status=200)

    # Verifico
    if data["transaction"]["application_code"] == "HOTG-EC-SERVER":
        print "CALLBACK: %s" % str(data)
        return __callback_paymentez_proc(data, 'ec')
    elif data["transaction"]["application_code"] == "HOTG-MX-SERVER":
        print "CALLBACK: %s" % str(data)
        return __callback_paymentez_proc(data, 'mx')
    else:
        print "CALLBACK_CLIENT: %s" % str(data)
        body = {"status": "error", "message": "ignoring callback: app_code"}
        return HttpResponse(json.dumps(body), content_type="application/json", status=200)


# CommerceGate Callback
@require_http_methods(["GET", "POST"])
def callback_commercegate(request):
    try:
        data            = request.body
        request_unquote = urllib.unquote_plus(data)
        xml             = xmltodict.parse(request_unquote[22:])
    except Exception:
        return HttpResponse('Error parsing callback data', content_type='text/plain', status='200')

    xml_data = xml['cgCallback']
    transaction_type = xml_data['TransactionType']
    transaction_id = xml_data['TransactionID']
    user_id = xml_data['UserID']

    try:
        user = User.objects.get(user_id=user_id)
    except ObjectDoesNotExist:
        return HttpResponse('UserId does not exist', content_type='text/plain', status='200')
    

    if 'TransactionReferenceID' in xml_data:
        transaction_reference_id = xml_data['TransactionReferenceID']

    if transaction_type == 'SALE':
        try:
            up = UserPayment.objects.filter(user=user, status='PE').order_by('-id')[0]
            ph = PaymentHistory.objects.filter(user_payment__user_payment_id=up.user_payment_id, status='P').order_by('-id')[0]
        except Exception as e:
            return HttpResponse('Error getting up or ph: %s' %e, content_type='text/plain', status='200')

        # Activar user payment
        up.active()
        up.payment_date = up.calc_payment_date(datetime.now())
        if up.is_trial:
            up.trial_counter -= 1
        up.save()

        # Aprobar payment history
        ph.approve(transaction_id)

        # Setear fecha de expiracion del usuario
        user.set_expiration(up.payment_date)

        print 'CommerceGate callback: Sale'

        # POST to promiscuus
        resp_promiscuus = post_to_promiscuus(ph, 'payment_commit')
        if resp_promiscuus['status'] == 'error':
            ph.message = "%s - Promiscuus error: %s" % (ph.message, resp_promiscuus['message'])
            ph.save()
        
    elif transaction_type == 'REBILL':
        up = UserPayment.objects.get(user=user, status='AC')
        payment_id = 'PH_%s_%d' % (user.user_id, int(time()))

        # Modificar fecha de user payment
        up.payment_date = up.calc_payment_date(datetime.now())
        up.save()

        # Modificar fecha de expiracion del usuario
        user.set_expiration(up.payment_date)

        # Obtengo integrador
        integrator = Integrator.get_by_country('commerce_gate', user.country)

        # Crear payment history
        ph = PaymentHistory.create(up, payment_id, integrator, status='A', gateway_id=transaction_id)
        
        if up.is_trial:
            up.trial_counter -= 1
            up.save()

        print 'CommerceGate callback: Rebill'

        # POST to promiscuus
        resp_promiscuus = post_to_promiscuus(ph, 'rebill')
        if resp_promiscuus['status'] == 'error':
            ph.message = "%s - Promiscuus error: %s" % (ph.message, resp_promiscuus['message'])
            ph.save()
        
    elif transaction_type == 'CANCELMEMBERSHIPNOTIFY':
        up = UserPayment.objects.get(user=user, status='AC')
        up.cancel('U')
        
        # POST to promiscuus
        resp_promiscuus = post_to_promiscuus(up, 'cancel')
        if resp_promiscuus['status'] == 'error':
            up.message = "%s - Promiscuus error: %s" % (up.message, resp_promiscuus['message'])
            up.save()    

        print 'CommerceGate callback: Cancel membership notify. User: %s' % user.user_id
        
    elif transaction_type == 'CANCELMEMBERSHIP':
        up = UserPayment.get_active(user)
        if up is not None:
            up.cancel('C')

            # POST to promiscuus
            resp_promiscuus = post_to_promiscuus(up, 'cancel')
            if resp_promiscuus['status'] == 'error':
                up.message = "%s - Promiscuus error: %s" % (up.message, resp_promiscuus['message'])
                up.save()

        user.expire()
        print 'CommerceGate callback: Cancel membership. User: %s' % user.user_id

    elif transaction_type == 'REFUND':
        try:
            ph = PaymentHistory.objects.get(gateway_id=transaction_reference_id)
            ph.cancel(transaction_id, 'refund')
        except:
            print 'Refund: Transaction ID %s not found' %transaction_reference_id

    print(xml)
    return HttpResponse('SUCCESS', content_type='text/plain', status='200')