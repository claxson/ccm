from json import dumps
import socket
import httplib2
import urlparse

import time

class Intercom(object):
    def __init__(self, ep, token):
        if ep is None:
            self.endpoint = 'https://api.intercom.io/events'
        else:
            self.endpoint = ep
        self.token = token
        self.h = httplib2.Http()

    def doPost(self, body):
        method = 'POST'
        uri = urlparse.urlparse(self.endpoint)
        return self.h.request(uri.geturl(), method, dumps(body),
                              {'Accept': 'application/json', 'Content-type': 'application/json', 'Authorization': 'Bearer %s' % self.token})

    def createUser(self, user_id, email, metadata):
        user = {"name": user_id, "email": email, "custom_attributes": metadata}
        temp_ep = self.endpoint
        self.endpoint = 'https://api.intercom.io/users'
        try:
            response, content = self.doPost(user)
            self.endpoint = temp_ep
            if response['status'] == '202':
                return True
            else:
                return False
        except socket.error as e:
            return False

    def submitEvent(self, user_id, email, event_name, metadata):
        self.createUser(user_id, email, metadata)

        event = {}
        event['name']       = user_id
        event['created_at'] = int(time.time())
        event['event_name'] = event_name
        event['email']      = email
        event['metadata']   = metadata

        try:
            response, content = self.doPost(event)
            if response['status'] == '202':
                return True
            else:
                return False
        except socket.error as e:
            return False