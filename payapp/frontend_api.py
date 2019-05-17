from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q, F
from django.db.models.functions import Lower
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, redirect

from models import User, UserPayment, PaymentHistory, Setting, Country, Integrator

import json
import logging

from datetime import timedelta, date, datetime
from intercom import Intercom
from misc import make_payment
from time import mktime

from httplib2 import Http

http_POST_OK = 201
http_REQUEST_OK = 200
http_NOT_FOUND = 404
http_BAD_REQUEST = 400
http_UNPROCESSABLE_ENTITY = 422
http_NOT_ALLOWED = 405
http_UNAUTHORIZED = 401
http_PAYMENT_REQUIRED = 402
http_INTERNAL_ERROR = 500
LIST_ROWS_DISPLAY = 20

# Boolean (Filter)
@require_http_methods(["GET"])
@login_required(login_url='login')
def filter_boolean(request):
    data = [ { 'key': 'Si', 'value': 'Si' }, { 'key': 'No', 'value': 'No' } ]

    body = { 'status': 'success', 'data': data }

    return HttpResponse(json.dumps(body, cls=DjangoJSONEncoder), content_type='application/json', status=http_REQUEST_OK)

# Get all countries (Filter)
@require_http_methods(["GET"])
@login_required(login_url='login')
def filter_countries(request):
    try:
        countries = Country.objects.all()
    except ObjectDoesNotExist:
        body = { 'status': 'error', 'message': 'No se puede consultar la lista de paises' }
        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)

    data = []

    for country in countries:
        ret             = {}
        ret['key']      = country.name
        ret['value']    = country.name

        data.append(ret)

    body = { 'status': 'success', 'data': data }

    return HttpResponse(json.dumps(body, cls=DjangoJSONEncoder), content_type='application/json', status=http_REQUEST_OK)

# Get recurrence all status (Filter)
@require_http_methods(["GET"])
@login_required(login_url='login')
def filter_status_recurrence(request):
    dict_status = dict(UserPayment.STATUS)

    data = []

    for key, value in dict_status.iteritems():
        ret             = {}
        ret['key']      = value
        ret['value']    = key

        data.append(ret)

    body = { 'status': 'success', 'data': data }

    return HttpResponse(json.dumps(body, cls=DjangoJSONEncoder), content_type='application/json', status=http_REQUEST_OK) 

# Get recurrencia (Filter)
@require_http_methods(["GET"])
@login_required(login_url='login')
def filter_recurrence(request):
    data = []

    prices = Setting.get_var('packages_recurrence').split(",")

    for price in prices:
        data.append({'key': price, 'value': price})

    body = { 'status': 'success', 'data': data }

    return HttpResponse(json.dumps(body, cls=DjangoJSONEncoder), content_type='application/json', status=http_REQUEST_OK) 

# Get all status history (Filter)
@require_http_methods(["GET"])
@login_required(login_url='login')
def filter_status_history(request):
    dict_status = dict(PaymentHistory.STATUS)

    data = []

    for key, value in dict_status.iteritems():
        ret             = {}
        ret['key']      = value
        ret['value']    = key

        data.append(ret)

    body = { 'status': 'success', 'data': data }

    return HttpResponse(json.dumps(body, cls=DjangoJSONEncoder), content_type='application/json', status=http_REQUEST_OK) 

# Get user by id
@require_http_methods(["GET"])
@login_required(login_url='login')
def get_user(request, user_id):
    try:
        user = User.objects.get(user_id=user_id)
    except ObjectDoesNotExist:
        body = { 'status': 'error', 'message': 'El usuario ' + user_id + ' no existe' }
        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)

    card = user.get_card()

    ret                     = {}
    ret['country']          = user.country.name
    ret['creation_date']    = user.creation_date
    ret['email']            = user.email
    ret['expiration']       = user.expiration
    ret['is_active']        = user.is_active
    ret['user_id']          = user_id

    if 'number' in card:
        ret['card'] = card.number

    body = { 'status': 'success', 'value': ret }
    return HttpResponse(json.dumps(body, cls=DjangoJSONEncoder), content_type='application/json', status=http_REQUEST_OK)

# Get all users (DataTables)
@require_http_methods(["GET"])
@login_required(login_url='login')
def get_all_users(request):
    try:
        records = User.objects.all().order_by('-modification_date')
    except ObjectDoesNotExist:
        body = { 'status': 'error', 'message': '' }
        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)

    datatables = request.GET
    draw = int(datatables['draw'])
    start = int(datatables['start'])
    length = int(datatables['length'])
    search = datatables['search[value]']
    records_total = records.count()
    records_filtered = records_total

    # Columns Dict
    columns_dic = {
        '3': 'country__name',
        '4': 'country__name'
    }

    # Filter
    def filter_table(filter_col, column_index):
        filter_input = filter_col.replace('^', '').replace('$', '')

        filtered_records = records.filter(**{ columns_dic[column_index]: filter_input })

        if column_index == '3':
            if filter_input == 'Si':
                filtered_records = records.filter(expiration__gt = date.today())
            elif filter_input == 'No':
                filtered_records = records.filter(expiration__lt = date.today())

        return filtered_records

    # Find Filters
    for key, value in columns_dic.iteritems():
        for param in datatables:
            if len(param) > 8 and param[8] == key:
                value = datatables['columns[' + key + '][search][value]']

                if value:
                    records = filter_table(value, key)
                    records_total = records.count()
                    records_filtered = records_total
                    break

    # Order Dict
    order_dic = {
        '0': 'user_id',
        '1': 'email',
        '4': 'country__name',
        '5': 'expiration',
    }

    # Order
    for param in datatables:
        if param[slice(5)] == 'order':
            column = datatables['order[0][column]']
            direction = datatables['order[0][dir]']

            if direction == 'desc':
                records = records.order_by('-' + order_dic[column])
            elif direction == 'asc':
                records = records.order_by(order_dic[column])
            break

    # Search
    if search:
        records = User.objects.filter(
                    Q(email__icontains = search) |
                    Q(user_id__icontains = search) |
                    Q(country__name__icontains = search) |
                    Q(expiration__icontains = search) |
                    Q(card__number__icontains = search)
                  )
        records_total = records.count()
        records_filtered = records_total

    # Paginator 
    paginator = Paginator(records, length)
    page_number = start / length + 1

    try:
        object_list = paginator.page(page_number).object_list
    except PageNotAnInteger:
        object_list = paginator.page(1).object_list
    except EmptyPage:
        object_list = paginator.page(1).object_list

    data = []

    for user in object_list:
        card = user.get_card()
        has_recurrence = user.has_recurrence()

        ret = {}
        ret['card']                 = ''
        ret['country']              = user.country.name
        ret['creation_date']        = user.creation_date
        ret['email']                = user.email
        ret['expiration']           = user.expiration
        ret['is_active']            = user.is_active
        ret['modification_date']    = user.modification_date
        ret['user_id']              = user.user_id
        ret['has_recurrence']       = has_recurrence

        if card:
            ret['card'] = card.number

        data.append(ret)

    body = { 
        'data': data,
        'draw': draw,
        'recordsFiltered': records_filtered,
        'recordsTotal': records_total,
    }

    return HttpResponse(json.dumps(body, cls=DjangoJSONEncoder), content_type='application/json', status=http_REQUEST_OK)

# Get user payment by user id
@require_http_methods(["GET"])
@login_required(login_url='login')
def get_user_payment(request, user_id, records='all'):
    try:
        if records == 'all':
            payments = UserPayment.objects.filter(
                user__user_id=user_id).order_by('-modification_date')
        else:
            payments = UserPayment.objects.filter(
                user__user_id=user_id).order_by('-modification_date')[:records]

        count = UserPayment.objects.filter(user__user_id=user_id).count()
    except ObjectDoesNotExist:
        body = { 'status': 'error', 'message': 'No existen pagos recurrentes para el usuario ' + user_id }
        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)

    value = []

    for payment in payments:
        ret = {}
        ret['amount']               = payment.amount
        ret['channel']              = payment.channel
        ret['creation_date']        = payment.creation_date
        ret['currency']             = payment.currency.name
        ret['disc_counter']         = payment.disc_counter
        ret['disc_pct']             = payment.disc_pct
        ret['enabled']              = payment.enabled
        ret['message']              = payment.message
        ret['modification_date']    = payment.modification_date
        ret['payday']               = payment.payday
        ret['recurrence']           = payment.recurrence
        ret['retries']              = payment.retries
        ret['status']               = payment.status

        value.append(ret)

    body = { 'status': 'success', 'data': value, 'records': count }
    return HttpResponse(json.dumps(body, cls=DjangoJSONEncoder), content_type='application/json', status=http_REQUEST_OK)

# Get all users payments (DataTables)
@require_http_methods(["GET"])
@login_required(login_url='login')
def get_all_payments(request):
    try:
        records = UserPayment.objects.all().order_by('-modification_date')
    except ObjectDoesNotExist:
        body = { 'status': 'error', 'message': 'No se puede consultar la lista de pagos recurrentes' }
        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)

    datatables = request.GET
    draw = int(datatables['draw'])
    length = int(datatables['length'])
    start = int(datatables['start'])
    search = datatables['search[value]']
    records_total = records.count()
    records_filtered = records_total

    # Columns Dict
    columns_dic = {
        '3': 'user__country__name',
        '4': 'user__country__name',
        '5': 'user__country__name',
        '6': 'recurrence',
        '7': 'user__country__name',
        '8': 'status',
    }

    # Filter
    def filter_table(filter_col, column_index):
        filter_input = filter_col.replace('^', '').replace('$', '')

        filtered_records = records.filter(**{ columns_dic[column_index]: filter_input })

        if len(filter_input) == 51:
            date_filter = filter_input.split(',')
            # modification_date
            if column_index == '4':
                filtered_records = records.filter(modification_date__range = [date_filter[0], date_filter[1]])
            # payment_date
            elif column_index == '5':
                filtered_records = records.filter(payment_date__range = [date_filter[0][slice(10)], date_filter[1][slice(10)]])

        # expiration
        if column_index == '7':
            if filter_col == 'true':
                filtered_records = records.filter(user__expiration__gt = date.today())
            elif filter_col == 'false':
                filtered_records = records.filter(user__expiration__lte = date.today())

        return filtered_records

    # Find Filters
    for key, value in columns_dic.iteritems():
        for param in datatables:
            if len(param) > 8 and param[8] == key:
                value = datatables['columns[' + key + '][search][value]']

                if value:
                    records = filter_table(value, key)
                    records_total = records.count()
                    records_filtered = records_total
                    break

    # Order Dict
    order_dic = {
        '0': 'user_id',
        '1': 'amount',
        '2': 'currency__name',
        '3': 'user__country__name',
        '4': 'modification_date',
        '5': 'payment_date',
        '6': 'recurrence',
        '8': 'status',
        '9': 'retries',
    }

    # Order
    for param in datatables:
        if param[slice(5)] == 'order':
            column = datatables['order[0][column]']
            direction = datatables['order[0][dir]']

            if direction == 'desc':
                records = records.order_by('-' + order_dic[column])
            elif direction == 'asc':
                records = records.order_by(order_dic[column])
            break

    # Search
    if search:
        records = UserPayment.objects.filter(
                    Q(user__user_id__icontains = search) |
                    Q(amount__icontains = search) |
                    Q(currency__name__icontains = search) |
                    Q(user__country__name__icontains = search) |
                    Q(recurrence__icontains = search) |
                    Q(retries__icontains = search) |
                    Q(message__icontains = search) |
                    Q(payment_date__icontains = search) |
                    Q(payday__icontains = search) |
                    Q(message__icontains = search)
                  )
        records_total = records.count()
        records_filtered = records_total

    # Paginator 
    paginator = Paginator(records, length)
    page_number = start / length + 1

    try:
        object_list = paginator.page(page_number).object_list
    except PageNotAnInteger:
        print 'PageNotAnInteger'
        object_list = paginator.page(1).object_list
    except EmptyPage:
        print 'EmptyPage'
        object_list = paginator.page(1).object_list

    countries = Country.get_all()
    data = []

    for payment in object_list:
        up_data = payment.user_payment_id.split("_")
        user_id = "%s_%s_%s" % (up_data[1], up_data[2], up_data[3])

        ret                         = {}
        ret['amount']               = payment.amount
        ret['channel']              = payment.channel
        ret['country']              = countries[up_data[1]]["name"]
        ret['creation_date']        = payment.creation_date
        ret['currency']             = countries[up_data[1]]["currency"]
        ret['disc_counter']         = payment.disc_counter
        ret['disc_pct']             = payment.disc_pct
        ret['enabled']              = payment.enabled
        ret['message']              = payment.message
        ret['is_active']            = payment.user.is_active
        ret['modification_date']    = payment.modification_date
        ret['payday']               = payment.payday
        ret['payment_date']         = payment.payment_date
        ret['recurrence']           = payment.recurrence
        ret['retries']              = payment.retries
        ret['status']               = payment.status
        ret['user_payment_id']      = payment.user_payment_id
        ret['user']                 = user_id

        data.append(ret)

    body = { 
        'data': data,
        'draw': draw,
        'recordsFiltered': records_filtered,
        'recordsTotal': records_total,
    }

    return HttpResponse(json.dumps(body, cls=DjangoJSONEncoder), content_type='application/json', status=http_REQUEST_OK)

# Get payment history by user id
@require_http_methods(["GET"])
@login_required(login_url='login')
def get_payment_history(request, user_payment_id, records='all'):
    try:
        if records == 'all':
            payments = PaymentHistory.objects.filter(
                user_payment__user_payment_id=user_payment_id).order_by('-modification_date')
        else:
            payments = PaymentHistory.objects.filter(
                user_payment__user_payment_id=user_payment_id).order_by('-modification_date')[:records]

        count = PaymentHistory.objects.filter(
            user_payment__user_payment_id=user_payment_id).count()

    except ObjectDoesNotExist:
        body = { 'status': 'error', 'message': 'No existe historial de pagos para el usuario ' + user_payment_id }
        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)

    value = []

    for payment in payments:
        payment.description = ''
        payment.code = ''

        try:
            data = json.loads(payment.message.replace("u'", "\"").replace("': '", "\": \"").replace("':", "\":").replace(
                "',", "\",").replace("'}", "\"}").replace("None", "null").replace("'", "").replace("u\"", "\""))

            if 'transaction' in data:
                if 'message' in data['transaction']:
                    payment.description = data['transaction']['message']
                if 'authorization_code' in data['transaction']:
                    payment.code = data['transaction']['authorization_code']
        except:
            print 'no message'

        ret = {}
        ret['amount']               = payment.amount
        ret['card']                 = ''
        ret['code']                 = payment.code
        ret['creation_date']        = payment.creation_date
        ret['description']          = payment.description
        ret['disc_pct']             = payment.disc_pct
        ret['gateway_id']           = payment.gateway_id
        ret['integrator']           = payment.integrator.name
        ret['manual']               = payment.manual
        ret['message']              = payment.message
        ret['modification_date']    = payment.modification_date
        ret['payment_id']           = payment.payment_id
        ret['status']               = payment.status
        ret['taxable_amount']       = payment.taxable_amount
        ret['user_payment_id']      = payment.user_payment.user_payment_id
        ret['user']                 = payment.user_payment.user.user_id
        ret['vat_amount']           = payment.vat_amount

        if payment.card:
            ret['card'] = payment.card.number

        value.append(ret)

    body = { 'status': 'success', 'data': value, 'records': count }
    return HttpResponse(json.dumps(body, cls=DjangoJSONEncoder), content_type='application/json', status=http_REQUEST_OK)

# Get all payments history (DataTables)
@require_http_methods(["GET"])
@login_required(login_url='login')
def get_all_payment_history(request):
    try:
        records = PaymentHistory.objects.all().order_by('-modification_date')
    except ObjectDoesNotExist:
        body = { 'status': 'error', 'message': 'No se puede consultar la lista de historial de pagos' }
        return HttpResponse(json.dumps(body), content_type='application/json', status=http_BAD_REQUEST)

    datatables = request.GET
    draw = int(datatables['draw'])
    length = int(datatables['length'])
    start = int(datatables['start'])
    search = datatables['search[value]']
    records_total = records.count()
    records_filtered = records_total

    # Columns Dict
    columns_dic = {
        '2': 'status',
        '4': 'status',
        '6': 'status',
    }

    # Filter
    def filter_table(filter_col, column_index):
        filter_input = filter_col.replace('^', '').replace('$', '')

        filtered_records = records.filter(**{ columns_dic[column_index]: filter_input })

        if filter_input == 'Si':
            filtered_records = records.filter(manual = True)
        elif filter_input == 'No':
            filtered_records = records.filter(manual = False)
        elif len(filter_input) == 51:
            date = filter_input.split(',')
            filtered_records = records.filter(modification_date__range = [date[0], date[1]])

        return filtered_records

    # Find Filters
    for key, value in columns_dic.iteritems():
        for param in datatables:
            if len(param) > 8 and param[8] == key:
                value = datatables['columns[' + key + '][search][value]']
                
                if value:
                    records = filter_table(value, key)
                    records_total = records.count()
                    records_filtered = records_total
                    break

    # Order Dict
    order_dic = {
        '0': 'user_payment__user__user_id',
        '1': 'gateway_id',
        '2': 'status',
        '3': 'amount',
        '4': 'modification_date',
        '6': 'manual',
    }

    # Order
    for param in datatables:
        if param[slice(5)] == 'order':
            column = datatables['order[0][column]']
            direction = datatables['order[0][dir]']

            if direction == 'desc':
                records = records.order_by('-' + order_dic[column])
            elif direction == 'asc':
                records = records.order_by(order_dic[column])

    # Search
    if search:
        records = PaymentHistory.objects.filter(
                    Q(user_payment__user__user_id__icontains = search) |
                    Q(gateway_id__icontains = search) |
                    Q(amount__icontains = search) |
                    Q(modification_date__icontains = search) |
                    Q(manual__icontains = search) |
                    Q(message__icontains = search)
                  )
        records_total = records.count()
        records_filtered = records_total

    # Paginator 
    paginator = Paginator(records, length)
    page_number = start / length + 1

    try:
        object_list = paginator.page(page_number).object_list
    except PageNotAnInteger:
        object_list = paginator.page(1).object_list
    except EmptyPage:
        object_list = paginator.page(1).object_list

    data = []

    for payment in object_list:
        payment.description = ''
        payment.code = ''

        try:
            message = json.loads(payment.message.replace("u'", "\"").replace("': '", "\": \"").replace("':", "\":").replace(
                "',", "\",").replace("'}", "\"}").replace("None", "null").replace("'", "").replace("u\"", "\""))

            if 'transaction' in message:
                if 'message' in message['transaction']:
                    payment.description = message['transaction']['message']
                if 'authorization_code' in message['transaction']:
                    payment.code = message['transaction']['authorization_code']
        except:
            print 'no message'

        ret = {}
        ret['amount']               = payment.amount
        ret['card']                 = ''
        ret['card_id']              = ''
        ret['code']                 = payment.code
        ret['creation_date']        = payment.creation_date
        ret['description']          = payment.description
        ret['disc_pct']             = payment.disc_pct
        ret['gateway_id']           = payment.gateway_id
        ret['integrator']           = payment.integrator.name
        ret['manual']               = payment.manual
        ret['message']              = payment.message
        ret['modification_date']    = payment.modification_date
        ret['payment_id']           = payment.payment_id
        ret['status']               = payment.status
        ret['taxable_amount']       = payment.taxable_amount
        ret['user_payment']         = payment.user_payment.user_payment_id
        ret['user']                 = payment.user_payment.user.user_id
        ret['vat_amount']           = payment.vat_amount

        if payment.card:
            ret['card'] = payment.card.number
            ret['card_id'] = payment.card.card_id

        data.append(ret)

    body = { 
        'data': data,
        'draw': draw,
        'recordsFiltered': records_filtered,
        'recordsTotal': records_total,
    }

    return HttpResponse(json.dumps(body, cls=DjangoJSONEncoder), content_type='application/json', status=http_REQUEST_OK)

@require_http_methods(["GET", "POST"])
@login_required(login_url='login')
def expireuser(request):
    if request.is_ajax():
        if request.method == 'GET':
            fecha = datetime.today()

        if request.method == 'POST':
            try:
                json_data       = json.loads(request.body)
                user_id         = json_data['user_id']
                user            = User.objects.get(user_id=user_id)
                fecha           = datetime.today()
                d               = timedelta(days=1)
                fecha          -= d
                user.expiration = fecha
                user.save()

                # Envio envento a intercom
                ep = Setting.get_var('intercom_endpoint')
                token = Setting.get_var('intercom_token')
                try:
                    intercom = Intercom(ep, token)
                    metadata = {"event_description": "usuario expirado por el administrador", "expire_at": str(
                        int(mktime(user.expiration.timetuple())))}
                    reply = intercom.submitEvent(
                        user.user_id, user.email, "user_expired", metadata)
                except Exception as e:
                    pass

                return JsonResponse({'message': 'Guardado correctamente', 'data': fecha}, status=200)
            except Exception as e:
                return JsonResponse({'message': 'Hubo un error', 'data': e.message}, status=500)
    return JsonResponse({'message': 'Metodo no permitido', 'data': ''}, status=500)

@require_http_methods(["POST"])
@login_required(login_url='login')
def activateuser(request):
    if request.is_ajax():
        if request.method == 'POST':
            try:
                json_data   = json.loads(request.body)
                user_id     = json_data['user_id']
                days        = json_data['days']
                user        = User.objects.get(user_id=user_id)

                # Sumar la cantidad de dias a hoy
                date = user.enable_for(days)

                # Envio evento a intercom
                ep = Setting.get_var('intercom_endpoint')
                token = Setting.get_var('intercom_token')

                try:
                    intercom = Intercom(ep, token)
                    metadata = {
                        'event_description': 'usuario activado por el administrador',
                        'expire_at': str(int(mktime(date.timetuple())))
                    }
                    reply = intercom.submitEvent(
                        user.user_id, user.email, 'user_activated', metadata)
                except Exception as e:
                    pass

                return JsonResponse({'message': 'activado correctamente'}, status=200)
            except Exception as e:
                return JsonResponse({'message': 'Hubo un error', 'data': e.message}, status=500)
    return JsonResponse({'message': 'Metodo no permitido', 'data': ''}, status=500)

@require_http_methods(["POST"])
@login_required(login_url='login')
def deleteuserpayment(request):
    if request.is_ajax():
        if request.method == 'POST':
            txtmessage = ''

            try:
                json_data = json.loads(request.body)

                if json_data['txtmessage']:
                    txtmessage = json_data['txtmessage']

                userpayment_id      = json_data['userpayment_id']
                registro            = UserPayment.objects.get(user_payment_id=userpayment_id)
                registro.message    = txtmessage
                registro.enabled    = False
                registro.status     = 'CA'
                registro.channel    = 'X'
                registro.save()

                # Envio cancelacion a CommerceGate
                integrator = Integrator.objects.get(country=registro.user.country)

                print '-- Integrador --'
                print integrator.name

                if integrator.name == 'commerce_gate':
                    url = 'https://ccm.hotgo.tv/api/v1/commercegate/set/cancel'
                    user_id = { 'user_id': registro.user.user_id }
                    data = json.dumps(user_id)
                    resp, content = Http().request(url, 'POST', body=data, headers={ 'content-type': 'application/json' })

                print '-- Respuesta --'
                print content

                # Envio envento a Intercom
                ep = Setting.get_var('intercom_endpoint')
                token = Setting.get_var('intercom_token')

                try:
                    intercom = Intercom(ep, token)
                    reply = intercom.submitEvent(registro.user.user_id, registro.user.email, "cancelled-sub",
                                                 {"event_description": "recurrencia cancelada por el administrador"})
                    if not reply:
                        registro.message = "Intercom error: cannot post the event"
                        registro.save()
                except Exception as e:
                    registro.message = "Intercom error: %s" % str(e)
                    registro.save()

                return JsonResponse({'message': 'activado correctamente'}, status=200)
            except Exception as e:
                return JsonResponse({'message': 'Hubo un error', 'data': e.message}, status=500)
    return JsonResponse({'message': 'Metodo no permitido', 'data': ''}, status=500)

@require_http_methods(["POST"])
@login_required(login_url='login')
def manual_payment(request):
    if request.is_ajax():
        if request.method == 'POST':
            try:
                json_data = json.loads(request.body)
                userpayment_id = json_data['userpayment_id']
                up = UserPayment.get_by_id(userpayment_id)

                if up is None:
                    return JsonResponse({'message': 'Error al realizar el pago, el usuario no existe'}, status=500)

                if up.user.has_active_recurrence():
                    return JsonResponse({'message': 'Error al realizar el pago: el usuario ya posee una recurrencia activa'}, status=500)

                logging.basicConfig(
                    format='%(asctime)s - manual_payments -[%(levelname)s]: %(message)s', filename=Setting.get_var('log_path'), level=logging.INFO)

                # Cambio a estado Pending
                up.status = 'PE'
                up.save()

                # Obtengo la tarjeta habilitada para el usuario
                card = up.user.get_card()

                if card is None:
                    msg = 'Error al obtener la tarjeta para el usuario'
                    up.error(msg)
                    return JsonResponse({'message': msg}, status=500)

                pay = make_payment(up, card, logging, True)

                if pay:
                    return JsonResponse({'message': 'Pago efectuado correctamente'}, status=200)
                else:
                    return JsonResponse({'message': 'Error al realizar el pago: verificar PaymentHistory'}, status=500)
            except Exception:
                return JsonResponse({'message': 'Hubo un error'}, status=500)
    return JsonResponse({'message': 'metodo no permitido'}, status=500)

@require_http_methods(["POST"])
@login_required(login_url='login')
def getuserpayment(request):
    if request.method == 'POST':
        if request.body:
            print '-- Request body --'
            print request.body
            try:
                up = UserPayment.get_by_id(request.body)
            except Exception as e:
                return JsonResponse({ 'message': 'Hubo un error', 'data': e.message }, status=500)

            return JsonResponse({ 'message': '', 'data': up.status }, status=200)
        else: 
            return JsonResponse({ 'message': 'El ID es mandatorio' }, status=500)
    else:
        return JsonResponse({ 'message': 'Metodo no permitido' }, status=500)