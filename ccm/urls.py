from django.conf.urls import url
from django.contrib import admin

from payapp.views import create_payment, payment_discount, cancel_payment, change_token_card, user_status, get_cards, get_enabled_card, change_user_email, refund, delete_card, payment_error
from payapp.frontend_api import get_user, get_all_users, get_user_payment, get_all_payments, get_payment_history, get_all_payment_history, expireuser, activateuser, deleteuserpayment, getuserpayment, manual_payment, filter_countries, filter_status_recurrence, filter_status_history, filter_recurrence, filter_boolean

from payapp.commercegate_views import payment_commercegate, cancel_commercegate, error_commercegate

from payapp.frontend_views import login_view, logout_view, dashboard, users, userpayments, paymenthistory, commercegate

from payapp.callback_views import callback_paymentez, callback_commercegate

from payapp.pagodigital_views import payment_pagodigital, userpayment_form_pagodigital, add_card_pagodigital, add_card_form_pagodigital

from payapp.prisma_views import payment_prisma_view, userpayment_form_prisma_view, add_card_prisma_view, add_card_form_prisma

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
