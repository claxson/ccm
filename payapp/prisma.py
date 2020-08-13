import requests
import json
import jsonschema

class PrismaException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class PrismaGateway(object):
    def __init__(self, endpoint, public_apikey, private_apikey):
        self.endpoint = endpoint
        self.public_apikey = public_apikey
        self.private_apikey = private_apikey
    
        self.payment_token_schema = {
                                        "type": "object",
                                        "properties": {
                                            "card_number": {"type": "string"},
                                            "card_expiration_month": {"type": "string"},
                                            "card_expiration_year": {"type": "string"},
                                            "security_code": {"type": "string"},
                                            "card_holder_name": {"type": "string"},
                                            "card_holder_identification": {
                                                "type": "object",
                                                "properties": {
                                                    "type": {"type": "string"},
                                                    "number": {"type": "string"}
                                                },
                                                "required": ["type", "number"]
                                            }
                                        },
                                        "required": ["card_number", "card_expiration_month", "card_expiration_year", "security_code", "card_holder_name"]
                                    }

        self.recurrence_token_schema =  {
                                            "type": "object",
                                            "properties": {
                                                "token": {"type": "string"},
                                                "security_code": {"type": "string"}
                                            },
                                            "required": ["token", "security_code"]
                                        }

        self.first_payment_schema = {
                                        "type": "object",
                                        "properties": {
                                            "customer": {
                                                "type": "object",
                                                "properties": {
                                                    "id": {"type": "string"},
                                                    "email": {"type": "string"}
                                                },
                                                "required": ["id", "email"]
                                            },
                                            "site_transaction_id": {"type": "string"},
                                            "token": {"type": "string"},
                                            "payment_method_id": {"type": "number"}, #revisar este dato
                                            "bin": {"type": "string"}, # primero 6 digitos de la tarjeta
                                            "amount": {"type": "number"}, 
                                            "currency": {"type": "string"}, # ARS
                                            "installments": {"type": "number"}, # cuotas del pago
                                            "payment_type": {"type": "string"} # single
                                        },
                                        "required": ["site_transaction_id", "token", "payment_method_id","bin",  
                                                     "amount", "currency", "installments", "payment_type"]
                                    }



    def get_payment_token(self, data):
        headers = {'Content-type': 'application/json',
                  'apikey': self.public_apikey}
        url = self.endpoint + "tokens"

        try:
            jsonschema.validate(instance=data, schema=self.payment_token_schema)
        except jsonschema.exceptions.ValidationError as err:
            raise PrismaException(err.message)
        print("------- get_payment_token --------")
        print("URL: " + url )
        print("DATA: " + json.dumps(data))

        try:
            response = requests.post(url, headers=headers, data=json.dumps(data))
        except Exception as err:
            raise PrismaException(err.message)

        print("RESPONSE: code: %d - content: %s" % (response.status_code, response.text))

        try:
            content = json.loads(response.text)
        except Exception as e:
            return False, {'status': 'error', 'message': str(e)}

        if response.status_code == 201:
            return True, content
        
        return False, content


    def get_recurrence_token(self, data):
        headers = {'Content-type': 'application/json',
                  'apikey': self.public_apikey}
        url = self.endpoint + "tokens"

        try:
            jsonschema.validate(instance=data, schema=self.recurrence_token_schema)
        except jsonschema.exceptions.ValidationError as err:
            raise PrismaException(err.message)

        print("------- get_recurrence_token --------")
        print("URL: " + url )
        print("DATA: " + json.dumps(data))

        try:
            response = requests.post(url, headers=headers, data=json.dumps(data))
        except Exception as err:
            raise PrismaException(err.message)

        print("RESPONSE: code: %d - content: %s" % (response.status_code, response.text))

        try:
            content = json.loads(response.text)
        except Exception as e:
            return False, {'status': 'error', 'message': str(e)}

        if response.status_code == 201:
            return True, content
        
        return False, content


    def payment(self, data):
        headers = {'Content-type': 'application/json',
                  'apikey': self.private_apikey}
        url = self.endpoint + "payments"

        try:
            jsonschema.validate(instance=data, schema=self.first_payment_schema)
        except jsonschema.exceptions.ValidationError as err:
            raise PrismaException(err.message)

        print("------- payment --------")
        print("URL: " + url )
        print("DATA: " + json.dumps(data))

        try:
            response = requests.post(url, headers=headers, data=json.dumps(data))
        except Exception as err:
            raise PrismaException(err.message)

        print("RESPONSE: code: %d - content: %s" % (response.status_code, response.text))

        try:
            content = json.loads(response.text)
        except Exception as e:
            return False, {'status': 'error', 'message': str(e)}

        if response.status_code == 201 or response.status_code == 402:
            return True, content
        
        return False, content

    def add_card(self, data):
        headers = {'Content-type': 'application/json',
                  'apikey': self.private_apikey}
        url = self.endpoint + "payments"

        try:
            jsonschema.validate(instance=data, schema=self.first_payment_schema)
        except jsonschema.exceptions.ValidationError as err:
            raise PrismaException(err.message)

        print("------- add card --------")
        print("URL: " + url )
        print("DATA: " + json.dumps(data))

        try:
            response = requests.post(url, headers=headers, data=json.dumps(data))
        except Exception as err:
            raise PrismaException(err.message)

        print("RESPONSE: code: %d - content: %s" % (response.status_code, response.text))

        try:
            content = json.loads(response.text)
        except Exception as e:
            return False, {'status': 'error', 'message': str(e)}

        if response.status_code == 201 or response.status_code == 402:
            if 'status' in content:
                if content['status'] == 'approved':
                    return True, content
                elif content['status'] == 'rejected':
                    message = "Add card error: %s" % content['status_details']['error']['type']
                    return False, {'status': 'error', 'message': message}
        
        return False, content


class PrismaTx(object):
    def __init__(self, user_id, user_email, tx_id, token, cc_bin, amount, payment_method_id):
        self.user_id = user_id
        self.user_email = user_email
        self.tx_id = tx_id
        self.token = token
        self.cc_bin = cc_bin
        self.amount = amount
        self.currency = 'ARS'
        self.payment_method_id = payment_method_id
        self.installments = 1
        self.payment_type = 'single'
        self.establishment_name = 'HotGo'
        self.sub_payments = []

    def serialize(self):
        s = {}
        s['customer'] = {'id': self.user_id, 'email': self.user_email}
        s['site_transaction_id'] = self.tx_id
        s['token'] = self.token
        s['payment_method_id'] = self.payment_method_id
        s['bin'] = self.cc_bin
        s['amount'] = self.amount
        s['currency'] = self.currency
        s['installments'] = self.installments
        s['payment_type'] = self.payment_type
        s['establishment_name'] = self.establishment_name
        s['sub_payments'] = self.sub_payments
        
        return s

class PrismaPaymentToken(object):
    def __init__(self, cc_number, cc_exp_month, cc_exp_year, cvv, cc_name, id_type, id_number):
        self.cc_number = cc_number
        self.cc_exp_month = cc_exp_month
        self.cc_exp_year = cc_exp_year
        self.cvv = cvv
        self.cc_name = cc_name
        self.id_type = id_type
        self.id_number = id_number
    
    def serialize(self):
        s = {}
        s['card_number'] = self.cc_number
        s['card_expiration_month'] = self.cc_exp_month
        s['card_expiration_year'] = self.cc_exp_year
        s['security_code'] = self.cvv
        s['card_holder_name'] = self.cc_name
        s['card_holder_identification'] = {'type': self.id_type, 'number': self.id_number}
       
        return s


    


if __name__ == "__main__":
    pg = PrismaGateway("https://developers.decidir.com/api/v2/", "sdfsd", "sdfsdf")
    data = '{"card_number": "4507990000004905", "card_expiration_month": "08", "card_expiration_year": "21", "security_code": "321", "card_holder_name": "John Doe", "card_holder_identification": {"type": "dni", "number": "25123456"}}'
    try:
        print(pg.get_payment_token(json.loads(data)))
    except Exception as e:
        print(e)