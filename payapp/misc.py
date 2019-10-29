#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Django
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from django.utils import timezone

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Settings
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from integrator_settings import PAYMENTEZ
from integrator_settings import PAGODIGITAL

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# App Model
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from payapp.models import Setting
from payapp.models import UserPayment
from payapp.models import Card
from payapp.models import Integrator
from payapp.models import IntegratorSetting
from payapp.models import PaymentHistory
from payapp.models import User

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Misc
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from payapp.paymentez import PaymentezGateway
from payapp.paymentez import PaymentezTx

from pagodigital import PagoDigitalGateway
from pagodigital import PagoDigitalTx
from pagodigital import PagoDigitalJWTGateway

#from payapp.intercom import Intercom

from time import time
from time import mktime
from datetime import timedelta


#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Promiscuus
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from promiscuus import Promiscuus

PAGODIGITAL_SUCCESS_CODES = ['000', '002', '003', '004', '005', '006', '007', '008', '009',
                             '00', '08', '11', '76', '77', '78', '79', '80', '81']


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
    ret = {"integrator": "pagodigital",
           "authorization_code": "",
           "id": "",
           "status_detail": "",
           "amount": "",
           "expire_at": ""}

    tr  = {"integrator": "integrator",
           "authorization_code": "NUMERO_AUTORIZACION",
           "id": "ID_REFERENCIA",
           "status_detail": "CODIGO_RESPUESTA",
           "amount": "amount",
           "expire_at": "expire_at"}

    for key in ret.keys():
        if tr[key] in data:
            ret[key] = data[tr[key]]

    return ret

    

def pagodigital_translator(content):
    ret = {}
    if "CODIGO_RESPUESTA" in content:
        code = content["CODIGO_RESPUESTA"]
    else:
        code = "-1"

    if str(code) in PAGODIGITAL_SUCCESS_CODES:
        code = '00'

    if code not in PAGODIGITAL["codes"]:
        code = "-1"

    data = PAGODIGITAL["codes"][str(code)]

    ret["up_status"]     = data["up_status"]
    
    if "MENSAJE_RESPUESTA" in content:
        ret["up_message"] = content["MENSAJE_RESPUESTA"]
    elif "ERROR" in content:
        ret["up_message"] = content["ERROR"]
    else:
        ret["up_message"] = ""

    if ret["up_message"] is None:
        ret["up_message"] = ""

    ret["up_recurrence"] = data["up_recurrence"]

    ret["ph_status"]    = data["ph_status"]

    if "ID_REFERENCIA" in content:
        ret["ph_gatewayid"] = content["ID_REFERENCIA"]
    else:
        ret["ph_gatewayid"] = ""
        
    ret["ph_message"]   = content

    ret["user_expire"]  = data["expire_user"]

    ret["user_message"] = data["user_msg"]

    ret["intercom"]     = data["intercom"]

    return ret


def post_to_intercom(ph, event, content):
    ep    = Setting.get_var('intercom_endpoint')
    token = Setting.get_var('intercom_token')
    
    try:
        intercom = Intercom(ep, token)
        reply = intercom.submitEvent(ph.user_payment.user.user_id, ph.user_payment.user.email, event, content)

        if not reply:
            ph.message = "%s - Intercom error: cannot post the event" % (ph.message)
            ph.save()
    except Exception as e:
        ph.message = "%s - Intercom error: %s" % (ph.message, str(e))
        ph.save()    

    return ph


def post_to_promiscuus(obj, event):
    ep = Setting.get_var('promiscuus_endpoint')
    api_key = Setting.get_var('promiscuus_apikey')
    source = Setting.get_var('promiscuus_source')
    p = Promiscuus(ep, api_key, source)

    PH_STATUS = {'A': 'approved', 'C': 'cancelled', 'R': 'rejected', 'E': 'error'}
    

    if event == 'payment_commit':
        access_until = User.get_expiration(obj.user_payment.user.user_id)
        try:
            ret = p.event_payment_commit(user_id=obj.user_payment.user.user_id,
                                        method_name=obj.integrator.name,
                                        payment_type='online',
                                        duration=obj.user_payment.recurrence,
                                        amount=obj.amount,
                                        discount=obj.disc_pct,
                                        is_suscription=True,
                                        access_until=access_until,
                                        status=PH_STATUS[obj.status],
                                        message=obj.user_payment.message)                                  
        except Exception as err:
            return {'status': 'error', 'message': err}


    elif event == 'rebill':
        if obj.manual:
            rebill_type = 'manual'
        else:
            rebill_type = 'auto'

        access_until = User.get_expiration(obj.user_payment.user.user_id)
        try:
            ret = p.event_rebill(user_id=obj.user_payment.user.user_id,
                                amount=obj.amount,
                                discount=obj.disc_pct,
                                rebill_type=rebill_type,
                                access_until=access_until,
                                status=PH_STATUS[obj.status],
                                message=obj.user_payment.message)                                  
        except Exception as err:
            return {'status': 'error', 'message': err}


    elif event == 'cancel':
        CHANNEL = {'E': '', 'U': 'user', 'R': 'reply', 'C': 'callback', 'T': 'timeout', 'F': 'refund', 'X': 'claxson'}
        access_until = User.get_expiration(obj.user.user_id)
        try:
            ret = p.event_cancel(user_id=obj.user.user_id,
                                channel=CHANNEL[obj.channel],
                                access_until=access_until)
                                                                          
        except Exception as err:
            return {'status': 'error', 'message': err}

    if ret.status_code == 201:
        return {'status': 'success'}
    else:
        return {'status': 'error', 'message': ret.text}

    
def paymentez_payment(up, card, logging, manual, amount):
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
    print(amount)
    # Creo el registro en PaymentHistory
    ph = PaymentHistory.create(up, payment_id, card.integrator, card, disc_pct, manual, '', 'P', amount)    
    logging.info("paymentez_payment(): Payment history created. ID: %s" % ph.payment_id)

    # Verico si es primer pago o rebill        
    if PaymentHistory.objects.filter(user_payment=up).count() == 1:
        promiscuus_event = 'payment_commit'            
    else:
        promiscuus_event = 'rebill'

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

        """
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
        """

        # POST to Promiscuus
        resp_promiscuus = post_to_promiscuus(ph, promiscuus_event)
        if resp_promiscuus['status'] == 'error':
            logging.info("paymentez_payment(): Promiscuus error: %s" % resp_promiscuus['message'])
            ph.message = "%s - Promiscuus error: %s" % (ph.message, resp_promiscuus['message'])
            ph.save()
        else:
            logging.info("paymentez_payment(): Promiscuus event sent")

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

        # POST to Promiscuus
        resp_promiscuus = post_to_promiscuus(ph, promiscuus_event)
        if resp_promiscuus['status'] == 'error':
            logging.info("paymentez_payment(): Promiscuus error: %s" % resp_promiscuus['message'])
            ph.message = "%s - Promiscuus error: %s" % (ph.message, resp_promiscuus['message'])
            ph.save()
        else:
            logging.info("paymentez_payment(): Promiscuus event sent")

        return False

        
def pagodigital_payment(up, card, logging, manual, amount):
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
    ph = PaymentHistory.create(up, payment_id, card.integrator, card, disc_pct, manual, '', 'P', amount)    
    logging.info("pagodigital_payment(): Payment history created. ID: %s" % ph.payment_id)

    # Verico si es primer pago o rebill        
    if PaymentHistory.objects.filter(user_payment=up).count() == 1:
        promiscuus_event = 'payment_commit'            
    else:
        promiscuus_event = 'rebill'
    
    if ph.amount > 0:
        
        # Obtengo settings del integrator
        api_key    = IntegratorSetting.get_var(card.integrator, 'api_key')
        api_secret = IntegratorSetting.get_var(card.integrator, 'api_secret')
        pd_tx_endpoint = IntegratorSetting.get_var(card.integrator, 'process_tx_endpoint')
        jwt_endpoint = IntegratorSetting.get_var(card.integrator, 'jwt_endpoint')
        jwt_user = IntegratorSetting.get_var(card.integrator, 'jwt_user')
        jwt_pass = IntegratorSetting.get_var(card.integrator, 'jwt_pass')

        # Obtengo el JWT
        pd_jwt_gw = PagoDigitalJWTGateway(jwt_endpoint, jwt_user, jwt_pass)
        try:
            ret, content = pd_jwt_gw.doPost()
            if not ret:
                message = 'Payment error: Error getting JWT'
                up.reply_error(message)
                ph.error('', message)
                return False
            if not 'TOKEN' in content:
                message = 'Payment error: Error getting JWT. JWT key not found' 
                up.reply_error(message)
                ph.error('', message)
                return False
            pd_jwt = content['TOKEN']
        except Exception as e:
            message = 'Payment error: Error getting JWT: %s' % e
            up.reply_error(message)
            ph.error('', message)
            return False

        # Realizar pago
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
        logging.info("pagodigital_payment(): Setting UserPayment values: status: %s - enabled: %s - message: %s"
                     % (pr["up_status"], str(pr["up_recurrence"]), pr["up_recurrence"]))
        if pr["up_status"] == 'ER':
            up.status = 'RE'
        else:
            up.status = pr["up_status"]
        up.message = pr["up_message"]
        up.enabled = pr["up_recurrence"]

        if up.status == 'AC':
            # calcular next_payment_day
            up.payment_date = up.calc_payment_date()
            # Fija la fecha de expiration del usuario
            logging.info("pagodigital_payment(): New user expiration %d for user %s" % (up.recurrence, up.user.user_id))
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
            logging.info("pagodigital_payment(): Payment executed with errors - UserPayment: %s - PaymentHistory: %s" % (up.user_payment_id, payment_id))
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
        """
        if pr["intercom"]["action"]:
            logging.info("pagodigital_payment(): Sending event to Intercom: %s" % pr["intercom"]["event"])
            content['amount'] = ph.amount
            if up.user.expiration is not None:
                content['expire_at'] = mktime(up.user.expiration.timetuple())
            ph = post_to_intercom(ph, pr["intercom"]["event"], pagodigital_intercom_metadata(content))               
        """

        # POST to Promiscuus
        resp_promiscuus = post_to_promiscuus(ph, promiscuus_event)
        if resp_promiscuus['status'] == 'error':
            logging.info("pagodigital_payment(): Promiscuus error: %s" % resp_promiscuus['message'])
            ph.message = "%s - Promiscuus error: %s" % (ph.message, resp_promiscuus['message'])
            ph.save()
        else:
            logging.info("pagodigital_payment(): Promiscuus event sent")

        logging.info("pagodigital_payment(): Payment executed succesfully - UserPayment: %s" % up.user_payment_id)
        return ret
    
    else:
        logging.info("pagodigital_payment(): Payment executed with errors - UserPayment: %s - PaymentHistory: %s" % (up.user_payment_id, payment_id))
        message = "%s - %s" % (content['STATUS_MESSAGE'], content['MESSAGE'])

        if manual:
            up.add_retry()
        up.reply_recurrence_error(message)
        ph.error('', content)

        # POST to Promiscuus
        resp_promiscuus = post_to_promiscuus(ph, promiscuus_event)
        if resp_promiscuus['status'] == 'error':
            logging.info("pagodigital_payment(): Promiscuus error: %s" % resp_promiscuus['message'])
            ph.message = "%s - Promiscuus error: %s" % (ph.message, resp_promiscuus['message'])
            ph.save()
        else:
            logging.info("pagodigital_payment(): Promiscuus event sent")

        return False
        
        
        
def make_payment(up, card, logging=None, manual=False, amount=None):
    if card.integrator.name == 'paymentez':
        ret = paymentez_payment(up, card, logging, manual, amount)
    elif card.integrator.name == 'pagodigital':
        ret = pagodigital_payment(up, card, logging, manual, amount)
    else:
        ret = False
    return ret
    
