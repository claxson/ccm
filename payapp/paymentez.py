from time     import time
from hashlib  import sha256
from base64   import b64encode
from httplib2 import Http
from json     import dumps
from json     import loads

import urlparse
import socket


'''
    order.description              Result
    Approved transaction           status = success, status_detail = 3
    Denied transaction             status = failure, status_detail = 9
    Reviewed transaction           status = failure, status_detail = 1
    Rejected by kount transaction  status = failure, status_detail = 11
    Card in black list             status = failure, status_detail = 12
'''


class GatewayException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class PaymentezGateway(object):
    def __init__(self,paymentez_server_application_code,paymentez_server_app_key,paymentez_endpoint):
        self.paymentez_server_app_key          = paymentez_server_app_key
        self.paymentez_server_application_code = paymentez_server_application_code
        self.paymentez_endpoint                = paymentez_endpoint
        self.h = Http()

    def get_auth_token(self):
        unix_timestamp    = str(int(time()))
        uniq_token_string = self.paymentez_server_app_key + unix_timestamp
        uniq_token_hash   = sha256(uniq_token_string).hexdigest()
        return b64encode('%s;%s;%s' % (self.paymentez_server_application_code,unix_timestamp, uniq_token_hash))

    def doPost(self,data):
        method = 'POST'
        header = {'Content-type': 'application/json', 'Auth-Token': self.get_auth_token()}
        uri = urlparse.urlparse(self.paymentez_endpoint) 

        try:
            response, content = self.h.request(uri.geturl(), method, data.to_str(), header)
        except socket.error as err:
            raise GatewayException(err)

        print "CONTENT: %s" % content
        if response['status'] == '200':
            return True, loads(content)
    
        return False, loads(content)


class PaymentezTx(object):
    def __init__(self, id, email, amount, description, dev_reference, taxable_amount, vat, token):
        self.id             = id
        self.email          = email
        self.amount         = amount
        self.description    = description
        self.dev_reference  = dev_reference
        self.taxable_amount = taxable_amount
        self.vat            = vat
        self.token          = token

    def serialize(self):
        s = {}
        s['user']  = {'id': self.id, 'email': self.email }
        s['order'] = {'amount': self.amount, 'description': self.description, 'dev_reference': self.dev_reference, 'vat': self.vat}
        if self.vat > 0:
            s['order']['taxable_amount'] = self.taxable_amount
        s['card']  = {'token': self.token}
        return s

    def to_dict(self):
        return self.serialize()

    def to_str(self):
        return dumps(self.serialize())


class PaymentezRefund(object):
    def __init__(self, id):
        self.id = id

    def serialize(self):
        s = {'transaction': {'id': self.id}}
        return s

    def to_dict(self):
        return self.serialize()

    def to_str(self):
        return dumps(self.serialize())


class DeleteCard(object):
    def __init__(self, token, user_id):
        self.token   = token
        self.user_id = user_id

    def serialize(self):
        s = {}
        s['card'] = {'token': self.token}
        s['user'] = {'id': self.user_id}
        return s

    def to_dict(self):
        return self.serialize()

    def to_str(self):
        return dumps(self.serialize())