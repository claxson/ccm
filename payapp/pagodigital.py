# -*- coding: utf-8 -*-
from httplib2 import Http
from urlparse import urlparse
import urllib
import socket
from json import loads
#import requests


class PagoDigitalException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class PagoDigitalJWTGateway(object):
    def __init__(self, endpoint, jwt_user, jwt_pass):
        self.endpoint = endpoint
        self.jwt_user = jwt_user
        self.jwt_pass = jwt_pass
        self.h = Http()

    def doPost(self):
        method = 'POST'
        header = {'Content-type': 'application/x-www-form-urlencoded'}
        
        data = {}
        data['JWT_USER'] = self.jwt_user
        data['JWT_PASS'] = self.jwt_pass
        
        try:
            body = urllib.urlencode(data)
            response, content = self.h.request(self.endpoint, method, body, header)
        except socket.error as err:
            raise PagoDigitalException(err)
        
        if response['status'] == '200':
            return True, loads(content)
    
        return False, loads(content)    


class PagoDigitalGateway(object):
    def __init__(self, endpoint, api_key, api_secret, jwt):
        self.endpoint = endpoint
        self.api_key = api_key
        self.api_secret = api_secret
        self.jwt = jwt
        self.h = Http()
        
    def doPost(self, data):
        method = 'POST'
        header = {'Content-type': 'application/x-www-form-urlencoded'}
        
        data['API_KEY'] = self.api_key
        data['API_SECRET'] = self.api_secret
        data['JWT'] = self.jwt
        
        try:
            body = urllib.urlencode(data)
            response, content = self.h.request(self.endpoint, method, body, header)
        except socket.error as err:
            raise PagoDigitalException(err)
        
        if response['status'] == '200':
            return True, loads(content)
    
        return False, loads(content)
 
        
class PagoDigitalTx(object):
    def __init__(self, amount, token, tax=0):
        self.amount = amount
        self.token = token
        self.tax = tax
        
    def serialize(self):
        s = {}
        s['AMOUNT'] = self.amount
        s['SUBTOTAL'] = self.amount
        s['TOKEN'] = self.token
        s['TAX'] = self.tax
        s['CUOTAS'] = '1'
        s['REFPAY'] = 'HOTGO'
        
        return s
        
    def to_dict(self):
        return self.serialize()


class PagoDigitalCard(object):
    def __init__(self, pan, cvv, fr, m_exp, y_exp, 
                 name, card_id, address, email, phone, city, state):
        self.pan = pan
        self.cvv = cvv
        self.fr = fr
        self.m_exp = m_exp
        self.y_exp = y_exp
        self.name = name
        self.card_id = card_id
        self.address = address
        self.email = email
        self.phone = phone
        self.city = city
        self.state = state
        
    def serialize(self):
        s = {}
        s['PAN'] = self.pan
        s['CVV2'] = self.cvv
        s['MES_EXP'] = self.m_exp
        s['ANO_EXP'] = self.y_exp
        s['NOMBRE'] = self.name.encode('utf-8')
        s['CEDULA'] = self.card_id
        s['DIRECCION'] = self.address.encode('utf-8')
        s['CORREO'] = self.email
        s['TELEFONO'] = self.phone
        s['CIUDAD'] = self.city.encode('utf-8')
        s['DEPARTAMENTO'] = self.state.encode('utf-8')
        s['FRANQUICIA'] = self.fr
    
        return s
    
    def to_dict(self):
        return self.serialize()
        
