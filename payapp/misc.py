#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Django
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from django.utils import timezone

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Settings
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from integrator_settings import PAYMENTEZ

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# App Model
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from payapp.models import Setting
from payapp.models import UserPayment
from payapp.models import Card
from payapp.models import Integrator
from payapp.models import IntegratorSetting
from payapp.models import PaymentHistory

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Misc
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

from payapp.paymentez import PaymentezGateway
from payapp.paymentez import PaymentezTx

from payapp.intercom import Intercom

from time import time
from time import mktime
from datetime import timedelta

def unicodetoascii(text):

    uni2ascii = {
            ord('\xe2\x80\x99'.decode('utf-8')): ord("'"),
            ord('\xe2\x80\x9c'.decode('utf-8')): ord('"'),
            ord('\xe2\x80\x9d'.decode('utf-8')): ord('"'),
            ord('\xe2\x80\x9e'.decode('utf-8')): ord('"'),
            ord('\xe2\x80\x9f'.decode('utf-8')): ord('"'),
            ord('\xc3\xa9'.decode('utf-8')): ord('e'),
            ord('\xe2\x80\x9c'.decode('utf-8')): ord('"'),
            ord('\xe2\x80\x93'.decode('utf-8')): ord('-'),
            ord('\xe2\x80\x92'.decode('utf-8')): ord('-'),
            ord('\xe2\x80\x94'.decode('utf-8')): ord('-'),
            ord('\xe2\x80\x94'.decode('utf-8')): ord('-'),
            ord('\xe2\x80\x98'.decode('utf-8')): ord("'"),
            ord('\xe2\x80\x9b'.decode('utf-8')): ord("'"),

            ord('\xe2\x80\x90'.decode('utf-8')): ord('-'),
            ord('\xe2\x80\x91'.decode('utf-8')): ord('-'),

            ord('\xe2\x80\xb2'.decode('utf-8')): ord("'"),
            ord('\xe2\x80\xb3'.decode('utf-8')): ord("'"),
            ord('\xe2\x80\xb4'.decode('utf-8')): ord("'"),
            ord('\xe2\x80\xb5'.decode('utf-8')): ord("'"),
            ord('\xe2\x80\xb6'.decode('utf-8')): ord("'"),
            ord('\xe2\x80\xb7'.decode('utf-8')): ord("'"),

            ord('\xe2\x81\xba'.decode('utf-8')): ord("+"),
            ord('\xe2\x81\xbb'.decode('utf-8')): ord("-"),
            ord('\xe2\x81\xbc'.decode('utf-8')): ord("="),
            ord('\xe2\x81\xbd'.decode('utf-8')): ord("("),
            ord('\xe2\x81\xbe'.decode('utf-8')): ord(")"),

                            }
    return text.decode('utf-8').translate(uni2ascii).encode('ascii')

def paymentez_translator(content):
    ret = {}
    if "status_detail" in content["transaction"]:
        code = content["transaction"]["status_detail"]
    else:
        code = "-1"

    data = PAYMENTEZ["paymentez"]["codes"][str(code)]
    if content["transaction"]["message"] is not None:
        content["transaction"]["message"] = unicodetoascii(content["transaction"]["message"].encode('utf-8'))
    else:
        content["transaction"]["message"] = ''

    ret["up_status"]     = data["up_status"]
    ret["up_message"]    = content["transaction"]["message"]
    ret["up_recurrence"] = data["up_recurrence"]

    ret["ph_status"]    = data["ph_status"]
    ret["ph_gatewayid"] = content["transaction"]["id"]
    ret["ph_message"]   = content

    ret["user_expire"]  = data["expire_user"]

    ret["user_message"] = data["user_msg"]

    ret["intercom"]     = data["intercom"]

    return ret


def paymentez_intercom_metadata(data):
    ret = {"integrator": "paymentez",
           "authorization_code": "",
           "id": "",
           "status_detail": "",
           "amount": "",
           "expire_at": ""}

    for key in ret.keys():
        if key in data:
            ret[key] = data[key]

    return ret
    
def pagodigital_intercom_metadata(data):
    ret = {"integrator": "paymentez",
           "authorization_code": "",
           "id": "",
           "status_detail": "",
           "amount": "",
           "expire_at": ""}

    for key in ret.keys():
        if key in data:
            ret[key] = data[key]

    return ret    
    

def post_to_intercom(ph, event, content):
    ep    = Setting.get_var('intercom_endpoint')
    token = Setting.get_var('intercom_token')
    if ph.user_payment.user.expiration is not None:
        content['transaction']['expire_at'] = mktime(ph.user_payment.user.expiration.timetuple())
    try:
        intercom = Intercom(ep, token)
        reply = intercom.submitEvent(ph.user_payment.user.user_id, ph.user_payment.user.email, event,
                                     pagodigital_intercom_metadata(content['transaction']))
        if not reply:
            ph.message = "%s - Intercom error: cannot post the event" % (ph.message)
            ph.save()
    except Exception as e:
        ph.message = "%s - Intercom error: %s" % (ph.message, str(e))
        ph.save()    

    return ph
    
def paymentez_payment(up, card, logging, manual):
    try:
        gw = PaymentezGateway(IntegratorSetting.get_var(card.integrator,'paymentez_server_application_code'),
                              IntegratorSetting.get_var(card.integrator,'paymentez_server_app_key'),
                              IntegratorSetting.get_var(card.integrator,'paymentez_endpoint'))
    except Exception as e:
        msg = "could not create user payment: (%s)" % str(e)
        up.error(msg)
        logging.error("paymentez_payment(): %s" % msg)
        return False

    # Aplico descuento si corresponde
    disc_flag = False
    if up.disc_counter > 0:
        disc_flag = True
        disc_pct  = up.disc_pct
        logging.info("paymentez_payment(): Calculating discount.")
    else:
        disc_pct = 0

    # Genero tx id sumando al userid el timestamp
    payment_id = "PH_%s_%d" % (up.user.user_id, int(time()))

    # Creo el registro en PaymentHistory
    ph = PaymentHistory.create(up, payment_id, card.integrator, card, disc_pct, manual)    
    logging.info("paymentez_payment(): Payment history created. ID: %s" % ph.payment_id)


    # Realizo el pago si amount mayor a 0
    if ph.amount > 0:
        try:
            logging.info("paymentez_payment(): Executing payment - User: %s - email: %s - "
                         "card: %s - payment_id: %s" % (up.user.user_id, up.user.email, card.token, ph.payment_id))
            resp, content = gw.doPost(PaymentezTx(up.user.user_id, up.user.email, ph.amount, 'HotGo',
                                             ph.payment_id, ph.taxable_amount, ph.vat_amount, card.token))
        except Exception as e:
            logging.info("paymentez_payment(): Communication error. New PaymentHistory status: Waiting Callback")
            # Pongo el pago en Waiting Callback
            ph.status = "W"
            ph.save()
            return False
    else:
        resp = True
        content = {'transaction': {'status_detail':'-10', 'id':'-10', 'message': 'Pago con descuento del 100%'}}
        #pr  = paymentez_translator(content)
    
    if resp:
        # Obtengo los valores segun la respuesta de Paymentez
        pr = paymentez_translator(content)
        # Seteo los valores de la UserPayment
        logging.info("paymentez_payment(): Setting UserPayment values: status: %s - enabled: %s - message: %s"
                     % (pr["up_status"], str(pr["up_recurrence"]), pr["up_recurrence"]))
        if pr["up_status"] == 'ER':
            up.status = 'RE'
        else:
            up.status = pr["up_status"]
        up.message = pr["up_message"]
        up.enabled = pr["up_recurrence"]

        if up.status == 'AC':
            # calcular next_payment_day
            if manual:
                up.payment_date = up.calc_payment_date(timezone.now())
            else:
                up.payment_date = up.calc_payment_date()
            # Fija la fecha de expiration del usuario
            logging.info("paymentez_payment(): New user expiration %d for user %s" % (up.recurrence, up.user.user_id))
            up.user.set_expiration(up.payment_date)
            if disc_flag:
                up.disc_counter = up.disc_counter - 1
            up.retries = 0
            ret = True
        else:
            if manual:
                up.retries = up.retries + 1
            else:
                # Agregar N dias a expiration
                delay = int(Setting.get_var('expiration_delay')) - 1
                user_expiration = up.user.expiration + timedelta(days=delay)
                up.user.set_expiration(user_expiration)
            up.channel = 'R'
            logging.info("paymentez_payment(): Payment executed with errors - UserPayment: %s - PaymentHistory: %s" % (up.user_payment_id, payment_id))
            ret = False
        up.save()

        # Seteo los valores del PaymentHistory
        logging.info("paymentez_payment(): Setting PaymentHistory values: status: %s - gateway_id: %s - message: %s"
                     % (pr["ph_status"], pr["ph_gatewayid"], pr["ph_message"]))
        ph.status = pr["ph_status"]
        ph.gateway_id = pr["ph_gatewayid"]
        ph.message = pr["ph_message"]
        ph.save()

        if pr["user_expire"]:
            logging.info("paymentez_payment(): Disabling user access to %s" % up.user.user_id)
            up.user.expire()

        if pr["intercom"]["action"]:
            logging.info("paymentez_payment(): Sending event to Intercom: %s" % pr["intercom"]["event"])
            ep = Setting.get_var('intercom_endpoint')
            token = Setting.get_var('intercom_token')
            if up.user.expiration is not None:
                content['transaction']['expire_at'] = str(int(mktime(up.user.expiration.timetuple())))
            try:
                intercom = Intercom(ep, token)
                reply = intercom.submitEvent(up.user.user_id, up.user.email, pr["intercom"]["event"],
                                             paymentez_intercom_metadata(content['transaction']))
                if not reply:
                    msg = "Intercom error: cannot post the event"
                    ph.message = "%s - %s" % (ph.message, msg)
                    logging.info("paymentez_payment(): %s" % msg)
                    ph.save()
            except Exception as e:
                msg = "Intercom error: %s" % str(e)
                ph.message = "%s - %s" % (ph.message, msg)
                logging.info("paymentez_payment(): %s" % msg)
                ph.save()

        logging.info("paymentez_payment(): Payment executed succesfully - UserPayment: %s" % up.user_payment_id)

        return ret

    else:
        logging.info("paymentez_payment(): Payment executed with errors - UserPayment: %s - PaymentHistory: %s" % (up.user_payment_id, payment_id))
        message = 'type: %s, help: %s, description: %s' % (content['error']['type'],
                                                           content['error']['help'],
                                                           content['error']['description'])
        if manual:
            up.add_retry()
        up.reply_recurrence_error(message)
        ph.error('', content)

        return False

        
def pagodigital_payment(up, card, logging, manual):
    # Aplico descuento si corresponde
    disc_flag = False
    if up.disc_counter > 0:
        disc_flag = True
        disc_pct  = up.disc_pct
        logging.info("pagodigital_payment(): Calculating discount.")
    else:
        disc_pct = 0
        
    # Genero tx id sumando al userid el timestamp
    payment_id = "PH_%s_%d" % (up.user.user_id, int(time()))

    # Creo el registro en PaymentHistory
    ph = PaymentHistory.create(up, payment_id, card.integrator, card, disc_pct, manual)    
    logging.info("pagodigital_payment(): Payment history created. ID: %s" % ph.payment_id)
    
    if ph.amount > 0:
        # Realizar pago
        pd_endpoint = IntegratorSetting.get_var(form.integrator, 'endpoint')
        pd_user     = IntegratorSetting.get_var(form.integrator, 'user')
        pd_password = IntegratorSetting.get_var(form.integrator, 'password')
        try:
            # ---- Hacer libreria para pago digital ----
            pass
        except Exception as e:
            # ---------- Analizar que pasa ante un error en el pago ---------------
            logging.info("pagodigital_payment(): Communication error. New PaymentHistory status: Waiting Callback")
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
        logging.info("pagodigitalz_payment(): Setting UserPayment values: status: %s - enabled: %s - message: %s"
                     % (pr["up_status"], str(pr["up_recurrence"]), pr["up_recurrence"]))
        up.status  = pr["up_status"]
        up.message = pr["up_message"]
        up.enabled = pr["up_recurrence"]

        if up.status == 'AC':
            # calcular next_payment_day
            up.payment_date = up.calc_payment_date()
            # Fija la fecha de expiration del usuario
            logging.info("pagodigital_payment(): New user expiration %d for user %s" % (up.recurrence, up.user.user_id))
            user.set_expiration(up.payment_date)
            if disc_flag:
                up.disc_counter = up.disc_counter - 1
            up.retries = 0
            ret = True
        else:
            if manual:
                up.retries = up.retries + 1
            else:
                # Agregar N dias a expiration
                delay = int(Setting.get_var('expiration_delay')) - 1
                user_expiration = up.user.expiration + timedelta(days=delay)
                up.user.set_expiration(user_expiration)
            logging.info("paymentez_payment(): Payment executed with errors - UserPayment: %s - PaymentHistory: %s" % (up.user_payment_id, payment_id))
            up.channel = 'R'
            ret = False
        up.save()       

        # Seteo los valores del PaymentHistory
        logging.info("pagodigital_payment(): Setting PaymentHistory values: status: %s - gateway_id: %s - message: %s"
                     % (pr["ph_status"], pr["ph_gatewayid"], pr["ph_message"]))
        ph.status     = pr["ph_status"]
        ph.gateway_id = pr["ph_gatewayid"]
        ph.message    = pr["ph_message"]
        ph.save()

        if pr["user_expire"]:
            user.expire()
            
        # Posteo en intercomo si es requerido
        if pr["intercom"]["action"]:
            logging.info("pagodigital_payment(): Sending event to Intercom: %s" % pr["intercom"]["event"])
            ph = post_to_intercom(ph, pr["intercom"]["event"], paymentez_intercom_metadata(content['transaction']))               

        logging.info("paymentez_payment(): Payment executed succesfully - UserPayment: %s" % up.user_payment_id)
        return ret
    
    else:
        logging.info("pagodigital_payment(): Payment executed with errors - UserPayment: %s - PaymentHistory: %s" % (up.user_payment_id, payment_id))
        message = 'type: %s, help: %s, description: %s' % (content['error']['type'],
                                                           content['error']['help'],
                                                           content['error']['description'])
        if manual:
            up.add_retry()
        up.reply_recurrence_error(message)
        ph.error('', content)

        return False
        
        
        
def make_payment(up, card, logging=None, manual=False):
    if card.integrator.name == 'paymentez':
        ret = paymentez_payment(up, card, logging, manual)
    elif card.integrator.name == 'pagodigital':
        ret = pagodigital_payment(up, card, logging, manual)
    else:
        ret = False
    return ret
    
