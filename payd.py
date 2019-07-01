import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ccm.settings")
django.setup()
from django.utils import timezone

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Base Exceptions
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import MultipleObjectsReturned 

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
import json
from datetime import datetime
from datetime import timedelta


from payapp.misc import paymentez_translator
from payapp.misc import paymentez_intercom_metadata
from payapp.misc import make_payment

from payapp.intercom import Intercom

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# System
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from daemon import Daemon
from sys    import exit
from sys    import argv

import logging
import time


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Basic Config
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
LOG_FILE = './log/payd.log'
ERR_FILE = './log/payd.err'
PID_FILE = './pid/payd.pid'


def load_settings():
    settings = {}

    try:
        settings['sleep_time_daemon'] = Setting.get_var('sleep_time_daemon')
    except ObjectDoesNotExist:
        logging.error("load_settings(): Setting with code sleep_time_daemon does not exist")
        return None

    return settings

"""
def get_card(user):
    try:
        card = Card.objects.get(user=user, enabled=True)
    except ObjectDoesNotExist:
        msg = "User %s has not card enabled" % user.user_id
        logging.error("get_card(): %s" % msg)
        return None
    except MultipleObjectsReturned:
        msg = "User %s has multiple cards enabled" % user.user_id
        logging.error("get_card(): %s" % msg)
        return None

    return card
"""

def paymentez_callback_checker(integrator):
    timeout = IntegratorSetting.get_var(integrator, 'callback_timeout')
    phs = PaymentHistory.objects.filter(status='W')
    logging.info("paymentez_callback_checker(): Checking callbacks expiration for %s %s..." % (integrator.name, integrator.country.name))
    for ph in phs:
        logging.info("paymentez_callback_checker(): PaymentHistory %s expired. New status... Error" % ph.payment_id)
        t = ph.modification_date + timezone.timedelta(seconds=int(timeout))
        if timezone.now() > t:
            ph.user_payment.timeout_error("callback timeout error")
            ph.status = 'E'
            ph.message = "callback timeout error"
            ph.save()

            logging.info("paymentez_callback_checker(): Sending event to Intercom: rejected-pay")
            ep = Setting.get_var('intercom_endpoint')
            token = Setting.get_var('intercom_token')
            try:
                metadata = {"integrator": "paymentez",
                            "authorization_code": "",
                            "id": "",
                            "status_detail": "timeout",
                            "amount": ""}
                intercom = Intercom(ep, token)
                reply = intercom.submitEvent(ph.user_payment.user.user_id,
                                             ph.user_payment.user.email,
                                             "rejected-pay",
                                             metadata)

                if not reply:
                    msg = "Intercom error: cannot post the event"
                    ph.message = "%s - %s" % (ph.message, msg)
                    logging.info("paymentez_callback_checker(): %s" % msg)
                    ph.save()
            except Exception as e:
                msg = "Intercom error: %s" % str(e)
                ph.message = "%s - %s" % (ph.message, msg)
                logging.info("paymentez_callback_checker(): %s" % msg)
                ph.save()


def payd_main():
    logging.basicConfig(format   = '%(asctime)s - payd.py -[%(levelname)s]: %(message)s',
                        filename = LOG_FILE,
                        level    = logging.INFO)

    settings = load_settings()
    if settings is None:
        exit(2)

    while True:
        # Obtengo todos los UserPayments activos y habilitados con payment_date vencido.
        logging.info("payd_main(): Getting active UserPayemnts to pay...")
        payments = UserPayment.objects.filter(status='AC', enabled=True, payment_date__lte=timezone.now(), internal=True)
        ips = Setting.get_var("payment_slot")
        print payments
        for up in payments:
            if ips > 0:
                # Cambio a Pending.
                up.status = 'PE'
                up.save()
                logging.info("payd_main(): UserPayment %s new status... Pending" % up.user_payment_id)

                # Obtengo la tarjeta habilitada para el usuario
                card = up.user.get_card()
                if card is None:
                    msg = "Error getting card for user %s" % up.user.user_id
                    up.error(msg)
                    continue

                make_payment(up, card, logging)
                ips = ips - 1
            else:
                pp = UserPayment.objects.filter(status='AC', enabled=True, payment_date__lte=timezone.now(), internal=True).count()
                logging.info("payd_main(): Payment slot limit reached. Next execution in %s seconds. Pending payments: %d"
                             % (str(settings['sleep_time_daemon']), pp))
                break

        # Verifico el estado de los callbacks para paymentez
        integrators = Integrator.objects.filter(name="paymentez")
        for integrator in integrators:
            paymentez_callback_checker(integrator)

        logging.info("payd_main(): Proccess complete. Next execution in %s seconds" % str(settings['sleep_time_daemon']))
        time.sleep(settings['sleep_time_daemon'])


class DaemonMain(Daemon):
    def run(self):
        try:
            payd_main()
        except KeyboardInterrupt:
            exit()


if __name__ == "__main__":
    daemon = DaemonMain(PID_FILE, stdout=LOG_FILE, stderr=ERR_FILE)
    if len(argv) == 2:
        if 'start'     == argv[1]:
            daemon.start()
        elif 'stop'    == argv[1]:
            daemon.stop()
        elif 'restart' == argv[1]:
            daemon.restart()
        elif 'run'     == argv[1]:
            daemon.run()
        elif 'status'  == argv[1]:
            daemon.status()
        else:
            print "Unknown command"
            exit(2)
        exit(0)
    else:
        print "usage: %s start|stop|restart|run" % argv[0]
        exit(2)
