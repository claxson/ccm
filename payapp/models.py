from __future__ import unicode_literals

from django.db import models
from datetime import datetime
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import *
import time
# Create your models here.

class Setting(models.Model):
    TYPES = (('I', 'Integer'),
             ('S', 'String'),
             ('F', 'Float'))

    key        = models.CharField(max_length=128, help_text='Configuration key')
    value      = models.CharField(max_length=128, help_text='Configuration value')
    dtype      = models.CharField(max_length=1, choices=TYPES, default='I', help_text='Data type')

    @classmethod
    def get_var(cls,key,cast=True):
        try:
            v = cls.objects.get(key=key)
            if cast:
                return v.cast()
            else:
                return v
        except ObjectDoesNotExist:
            return None

    def cast(self):
        if self.dtype == 'I':
            return int(self.value)
        if self.dtype == 'F':
            return float(self.value)
        if self.dtype == 'S':
            return self.value

    def __unicode__(self):
        return self.key


class Currency(models.Model):
    name = models.CharField(max_length=64)
    code = models.CharField(max_length=3)

    def __unicode__(self):
        return self.name


class Country(models.Model):
    name       = models.CharField(max_length=128)
    code       = models.CharField(max_length=2)
    currency   = models.ForeignKey(Currency)
    tax        = models.FloatField(default=0, help_text="Example: 21% = 1.21")
    full_price = models.BooleanField(default=True, help_text="True if taxes included in price")

    def __unicode__(self):
        return self.name


class Integrator(models.Model):
    METHOD = (('TO', 'TOKEN'),
              ('DI', 'DIRECT'))

    name    = models.CharField(max_length=32)
    country = models.ForeignKey(Country)
    method  = models.CharField(max_length=2, choices=METHOD, default='TO')

    def __unicode__(self):
        return self.name


class IntegratorSetting(models.Model):
    TYPES = (('I', 'Integer'),
             ('S', 'String'),
             ('F', 'Float'))

    integrator = models.ForeignKey(Integrator)
    key        = models.CharField(max_length=128, help_text='Configuration key')
    value      = models.CharField(max_length=128, help_text='Configuration value')
    dtype      = models.CharField(max_length=1, choices=TYPES, default='I', help_text='Data type')

    @classmethod
    def get_var(cls,integrator,key,cast=True):
        try:
            i = Integrator.objects.get(name=integrator)
            v = cls.objects.get(integrator=i, key=key)
            if cast:
                return v.cast()
            else:
                return v
        except ObjectDoesNotExist:
            return None

    def cast(self):
        if self.dtype == 'I':
            return int(self.value)
        if self.dtype == 'F':
            return float(self.value)
        if self.dtype == 'S':
            return self.value

    def __unicode__(self):
        return "%s:%s" % (self.integrator.name, self.key)


class User(models.Model):
    user_id           = models.CharField(max_length=128)
    email             = models.CharField(max_length=128)
    country           = models.ForeignKey(Country)
    expiration        = models.DateTimeField(auto_now_add=True)
    creation_date     = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __unicode__(self):
        return self.user_id
        
    @classmethod
    def create(cls, user_id, email, country):
        us         = cls()
        us.user_id = user_id
        us.email   = email
        us.country = country        
        us.save()
        return us
    
    def add_to_expiration(self, days):
        self.expiration = timezone.now() + timezone.timedelta(days=days)
        self.save()

    def has_expired(self):
        if self.expiration < timezone.now():
            return True
        else:

            return False


class UserPayment(models.Model):
    STATUS = (('PE', 'Pending'),
              ('AC', 'Active'),
              ('CA', 'Cancelled'),
              ('ER', 'Error'))

    CHANNEL = (('E', ''),
               ('U', 'User'),
               ('R', 'Reply'),
               ('C', 'Callback'),
               ('T', 'Timeout'))

    user_payment_id   = models.CharField(max_length=128)
    user              = models.ForeignKey(User)
    amount            = models.FloatField(default=0)
    currency          = models.ForeignKey(Currency)
    payment_date      = models.DateField(auto_now_add=False, help_text='Next payment date')
    payday            = models.IntegerField(help_text='Payday number')
    recurrence        = models.IntegerField(help_text="Monthly recurrence")
    disc_pct          = models.IntegerField(default=0, help_text="Discount percentage")
    disc_counter      = models.IntegerField(default=0, help_text="Payments with discount remaining")
    status            = models.CharField(max_length=2, choices=STATUS, default='PE', help_text='Payment status')
    channel           = models.CharField(max_length=1, choices=CHANNEL, default='E', help_text='Error or cancellation channel')
    message           = models.CharField(max_length=1024, blank=True)
    enabled           = models.BooleanField(default=True)
    creation_date     = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __unicode__(self):
        return self.user_payment_id
        
    @classmethod
    def create(cls, user, amount, currency, payment_date, payday, recurrence, discount=0, disc_counter=0):
        up = cls()
        up.user_payment_id = "UP_%s_%d" % (user.user_id, int(time.time()))
        up.user            = user
        up.amount          = float(amount)
        up.currency        = currency
        if payment_date == 0 or payment_date == 0.0 or payment_date == '0':
            np = timezone.now() + timezone.timedelta(days=int(recurrence))
            if int(recurrence) >= 30:
                up.payment_date = datetime(np.year,np.month,payday)
            else:
                up.payment_date = datetime(np.year,np.month,np.day)
            up.status       = 'PE'
        else:
            up.payment_date = datetime.fromtimestamp(int(payment_date))
            up.status       = 'AC'
        up.payday       = payday
        up.recurrence   = recurrence
        up.disc_pct     = discount
        up.disc_counter = disc_counter
        up.enabled      = True
        up.save()
        return up
    
    def discount(self, discount, disc_counter):
        self.disc_pct     = discount
        self.disc_counter = disc_counter
        self.save()
        
    def disable(self):
        self.enabled = False
        self.save()
    
    def enable(self):
        self.enabled = True
        self.save()
    
    def reply_error(self, message=''):
        self.status  = 'ER'
        self.message = message
        self.enabled = False
        self.channel = 'R'
        self.save()

    def callback_error(self, message=''):
        self.status  = 'ER'
        self.message = message
        self.enabled = False
        self.channel = 'C'
        self.save()

    def timeout_error(self, message=''):
        self.status  = 'ER'
        self.message = message
        self.enabled = False
        self.channel = 'T'
        self.save()

    def cancel(self):
        self.enabled = False
        self.status  = 'CA'
        self.channel = 'U'
        self.save()

    def calculate_discount(self):
        return  self.amount - (self.amount * self.disc_pct / 100)


class Card(models.Model):
    card_id           = models.CharField(max_length=128)
    user              = models.ForeignKey(User)
    number            = models.CharField(max_length=64, blank=True)
    card_type         = models.CharField(max_length=128, blank=True)
    name              = models.CharField(max_length=128, blank=True)
    expiration        = models.CharField(max_length=5, blank=True, help_text="MM/AA")
    cvc               = models.CharField(max_length=8, blank=True)
    token             = models.CharField(max_length=256, blank=True)
    integrator        = models.ForeignKey(Integrator)
    enabled           = models.BooleanField(default=False)
    creation_date     = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __unicode__(self):
        return self.card_id
    
    @classmethod
    def create_with_token(cls, user, token, number, expiration, integrator):
        cd            = cls()
        cd.card_id    = "CD_%s_%d" % (user.user_id, int(time.time()))
        cd.user       = user
        cd.token      = token
        cd.number     = number
        cd.expiration = expiration
        cd.integrator = integrator
        cd.enabled    = True
        cd.save()
        return cd
    
    def enable(self):
        self.enabled = True
        self.save()
        
    def disable(self):
        self.enabled = False
        self.save()

class PaymentHistory(models.Model):
    STATUS = (('P', 'Processing'),
              ('W', 'Waiting callback'),
              ('A', 'Approved'),
              ('R', 'Rejected'),
              ('E', 'Error'))

    user_payment      = models.ForeignKey(UserPayment)
    card              = models.ForeignKey(Card)
    status            = models.CharField(max_length=1, choices=STATUS, default='P')
    payment_id        = models.CharField(max_length=128, help_text='Internal ID')
    gateway_id        = models.CharField(max_length=128, blank=True, null=True, help_text='External ID')
    amount            = models.FloatField(help_text='amount=net_amount + tax_amount')
    vat_amount        = models.FloatField(default=0, help_text='Tax amount')
    taxable_amount    = models.FloatField(default=0, help_text='Net amount')
    disc_pct          = models.IntegerField(default=0, help_text="Discount percentage")
    message           = models.CharField(max_length=512, blank=True)
    creation_date     = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __unicode__(self):
        return self.payment_id

    def __amounts_calculator(self):
        ret = {}
        tax = self.user_payment.user.country.tax
        if tax > 0:
            if self.user_payment.user.country.full_price:
                amount         = self.user_payment.amount
                taxable_amount = round(amount / tax, 2)
                vat_amount     = amount - taxable_amount
            else:
                taxable_amount = self.user_payment.amount
                amount         = taxable_amount * tax
                vat_amount     = amount - taxable_amount
        else:
            amount         = self.user_payment.amount
            taxable_amount = 0
            vat_amount     = 0

        return {'amount': amount, 'taxable_amount': taxable_amount, 'vat_amount': vat_amount}


    @classmethod
    def create(cls, user_payment, card, payment_id, amount, disc_pct=0 ,gateway_id='', status='P'):
        ph = cls()
        ph.user_payment   = user_payment
        amounts = ph.__amounts_calculator()

        ph.card           = card
        ph.status         = status
        ph.payment_id     = payment_id
        ph.gateway_id     = gateway_id
        ph.amount         = amounts['amount']
        ph.vat_amount     = amounts['vat_amount']
        ph.taxable_amount = amounts['taxable_amount']
        ph.disc_pct       = disc_pct
        ph.save()
        return ph

    def approve(self, gw_id=''):
        self.status     = 'A'
        self.gateway_id = gw_id
        self.save()

    def reject(self, message=''):
        self.status  = 'R'
        self.message = message
        self.save()

    def error(self, message=''):
        self.status  = 'E'
        self.message = message
        self.save()

    def __unicode__(self):
        return "%s" % (self.payment_id)



