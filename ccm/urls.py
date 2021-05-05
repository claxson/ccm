from django.conf.urls import url
from django.contrib import admin

# Paymentez and General Views
from payapp.views import create_payment
from payapp.views import payment_discount
from payapp.views import cancel_payment
from payapp.views import change_token_card
from payapp.views import user_status
from payapp.views import get_cards
from payapp.views import get_enabled_card
from payapp.views import change_user_email
from payapp.views import refund
from payapp.views import delete_card
from payapp.views import payment_error

# Frontend API
from payapp.frontend_api import get_user
from payapp.frontend_api import get_all_users
from payapp.frontend_api import get_user_payment
from payapp.frontend_api import get_all_payments
from payapp.frontend_api import get_payment_history
from payapp.frontend_api import get_all_payment_history
from payapp.frontend_api import expireuser
from payapp.frontend_api import activateuser
from payapp.frontend_api import deleteuserpayment
from payapp.frontend_api import getuserpayment
from payapp.frontend_api import manual_payment
from payapp.frontend_api import filter_countries
from payapp.frontend_api import filter_status_recurrence
from payapp.frontend_api import filter_status_history
from payapp.frontend_api import filter_recurrence
from payapp.frontend_api import filter_boolean

# Frontend Views
from payapp.frontend_views import login_view
from payapp.frontend_views import logout_view
from payapp.frontend_views import dashboard
from payapp.frontend_views import users
from payapp.frontend_views import userpayments
from payapp.frontend_views import paymenthistory
from payapp.frontend_views import commercegate

# CommerceGata
from payapp.commercegate_views import payment_commercegate
from payapp.commercegate_views import cancel_commercegate
from payapp.commercegate_views import error_commercegate

# Callbacks
from payapp.callback_views import callback_paymentez
from payapp.callback_views import callback_commercegate
#from payapp.callback_views import callback_tatix

# PagoDigital
from payapp.pagodigital_views import payment_pagodigital
from payapp.pagodigital_views import userpayment_form_pagodigital
from payapp.pagodigital_views import add_card_pagodigital
from payapp.pagodigital_views import add_card_form_pagodigital

# Prisma
from payapp.prisma_views import payment_prisma_view
from payapp.prisma_views import userpayment_form_prisma_view
from payapp.prisma_views import add_card_prisma_view
from payapp.prisma_views import add_card_form_prisma

# Tatix
"""
from payapp.tatix_views import form_tatix_view
from payapp.tatix_views import payment_tatix_view
from payapp.tatix_views import reactivate_userpayment_tatix_view
from payapp.tatix_views import cancel_tatix_view
from payapp.tatix_views import apply_discount_tatix_view
from payapp.tatix_views import callback_tatix_view
"""

urlpatterns = [

    url(r'^admin/', admin.site.urls),
    url(r'^api/v1/set/userpayment', create_payment),
    url(r'^api/v1/set/discount', payment_discount),
    url(r'^api/v1/set/cancel', cancel_payment),
    url(r'^api/v1/set/changecard', change_token_card),
    url(r'^api/v1/set/changeemail', change_user_email),
    url(r'^api/v1/get/deletecard/(?P<token>[\w\-]+)', delete_card),
    url(r'^api/v1/get/userstatus/(?P<user_id>[\w\-]+)', user_status),
    url(r'^api/v1/callback/paymentez/', callback_paymentez),
    url(r'^api/v1/get/cards/(?P<user_id>[\w\-]+)', get_cards),
    url(r'^api/v1/get/enabledcard/(?P<user_id>[\w\-]+)', get_enabled_card),
    url(r'^api/v1/get/refund/(?P<payment_id>[\w\-]+)', refund),

    # Commerce Gate
    url(r'^api/v1/callback/commercegate', callback_commercegate),
    url(r'^api/v1/commercegate/get/form', payment_commercegate),
    url(r'^api/v1/commercegate/set/cancel', cancel_commercegate),
    url(r'^commercegate/error/(?P<user_payment_id>[\w\-]+)', error_commercegate),
    
    # Pago Digital
    url(r'^api/v1/pagodigital/set/payment', payment_pagodigital),
    url(r'^api/v1/pagodigital/userpayment/form', userpayment_form_pagodigital),
    url(r'^api/v1/pagodigital/set/addcard', add_card_pagodigital),
    url(r'^api/v1/pagodigital/addcard/form', add_card_form_pagodigital),

    # Prisma
    url(r'^api/v1/prisma/set/payment', payment_prisma_view),
    url(r'^api/v1/prisma/userpayment/form', userpayment_form_prisma_view),
    url(r'^api/v1/prisma/set/addcard', add_card_prisma_view),
    url(r'^api/v1/prisma/addcard/form', add_card_form_prisma),

    
    # Tatix
    #url(r'^api/v1/tatix/set/payment', payment_tatix_view),
    #url(r'^api/v1/tatix/userpayment/form', form_tatix_view),
    #url(r'^api/v1/tatix/userpayment/reactivate/(?P<user_id>[\w\-]+)', reactivate_userpayment_tatix_view),
    #url(r'^api/v1/tatix/userpayment/cancel/(?P<user_id>[\w\-]+)', cancel_tatix_view),
    #url(r'^api/v1/tatix/userpayment/discount', apply_discount_tatix_view),
    #url(r'^api/v1/tatix/callback', callback_tatix),
    
    url(r'^api/v1/api/users/(?P<user_id>[\w\-]+)', get_user),
    url(r'^api/v1/api/users', get_all_users),
    url(r'^api/v1/api/payments/(?P<user_id>[\w\-]+)/(?P<records>[\w\-]+)', get_user_payment),
    url(r'^api/v1/api/payments', get_all_payments),
    url(r'^api/v1/api/paymenthistory/(?P<user_payment_id>[\w\-]+)/(?P<records>[\w\-]+)', get_payment_history),
    url(r'^api/v1/api/paymenthistory', get_all_payment_history),

    url(r'^api/v1/api/filter/boolean', filter_boolean),
    url(r'^api/v1/api/filter/countries', filter_countries),
    url(r'^api/v1/api/filter/recurrence', filter_recurrence),
    url(r'^api/v1/api/filter/status-recurrence', filter_status_recurrence),
    url(r'^api/v1/api/filter/status-paymenthistory', filter_status_history),

    # Management
    url(r'^ui/dashboard/', dashboard, name='dashboard'),

    url(r'^ui/expireuser', expireuser, name='expireuser'),
    url(r'^ui/activateuser', activateuser, name='activateuser'),	
    url(r'^ui/deleteuserpayment', deleteuserpayment, name='deleteuserpayment'),
    url(r'^ui/manualpayment', manual_payment, name='manual_payment'),
    url(r'^ui/getuserpayment', getuserpayment, name='getuserpayment'),

    url(r'^ui/login/', login_view, name='login'),
    url(r'^ui/logout/', logout_view, name='logout'),

    url(r'^ui/usuarios/', users, name='users'),
    url(r'^ui/pagos-recurrentes/', userpayments, name='userpayments'),
    url(r'^ui/historial-pagos/', paymenthistory, name='paymenthistory'),

    url(r'^payment/error/', payment_error),
    
]
