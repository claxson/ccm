import requests
import json

class Promiscuus(object):
    def __init__(self, url = None, apikey = None, source = None):
        self.service_url = url
        self.apikey = apikey
        self.source = source

    def post(self, data):
        header = {'Content-type': 'application/json', 'x-api-key': self.apikey}

        if self.service_url is not None:
            return requests.post(self.service_url, data=json.dumps(data), headers=header)

    def __loader(self, keys, args):
        ret = {}
        for key, value in args.items():
            if key in keys:
                if value is not None and value != '':
                    ret[key] = value
        ret['source'] = self.source
        return ret

    def event_cancel(self, **kwargs):
        keys = ['user_id', 'channel', 'access_until']
        if 'user_id' in kwargs:
            data = self.__loader(keys, kwargs)
            data['event'] = 'cancel'
            return self.post(data)
        else:
            raise Exception('Mandatory field is missing: \"user_id\"')

    def event_payment_selection(self, **kwargs):
        keys = ['user_id', 'method_name', 'payment_type', 'package', 'duration', 'amount', 'discount']
        if 'user_id' in kwargs:
            data = self.__loader(keys, kwargs)
            data['event'] = 'payment_selection'
            return self.post(data)
        else:
            raise Exception('Mandatory field is missing: \"user_id\"')

    def event_payment_commit(self, **kwargs):
        keys = ['user_id', 'method_name', 'payment_type', 'package', 'duration', 'amount', 'discount', 'is_suscription', 'access_until', 'status', 'message']
        if 'user_id' in kwargs:
            data = self.__loader(keys, kwargs)
            data['event'] = 'payment_commit'
            return self.post(data)
        else:
            raise Exception('Mandatory field is missing: \"user_id\"')

    def event_rebill(self, **kwargs):
        keys = ['user_id', 'amount', 'access_until', 'status', 'message', 'discount', 'rebill_type']
        if 'user_id' in kwargs:
            data = self.__loader(keys, kwargs)
            data['event'] = 'rebill'
            return self.post(data)
        else:
            raise Exception('Mandatory field is missing: \"user_id\"')

    def event_poll(self, **kwargs):
        keys = ['user_id', 'selection', 'comments']
        if 'user_id' in kwargs:
            data = self.__loader(keys, kwargs)
            data['event'] = 'poll'
            return self.post(data)
        else:
            raise Exception('Mandatory field is missing: \"user_id\"')

    def event_discount(self, **kwargs):
        keys = ['user_id', 'discount', 'counter']
        if 'user_id' in kwargs:
            data = self.__loader(keys, kwargs)
            data['event'] = 'discount'
            return self.post(data)
        else:
            raise Exception('Mandatory field is missing: \"user_id\"')