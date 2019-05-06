from __future__ import unicode_literals

from django.db import models
from datetime import datetime, date
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import MultipleObjectsReturned

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

    def natural_key(self):
        return (self.name)

    def __unicode__(self):
        return self.name


class Country(models.Model):
    name       = models.CharField(max_length=128)
    code       = models.CharField(max_length=2)
    currency   = models.ForeignKey(Currency)
    tax        = models.FloatField(default=0, help_text="Example: 21% = 1.21")
    full_price = models.BooleanField(default=True, help_text="True if taxes included in price")

    def natural_key(self):
        return (self.name)

    def __unicode__(self):
        return self.name

    @classmethod
    def get(cls, name):
        try:
            return cls.objects.get(name=name)
        except Exception:
            return None

    @classmethod
    def get_all(cls):
        countries = cls.objects.all()
        ret = {}
        for country in countries:
            ret[country.code.upper()] = {"name": country.name, "currency": country.currency.name}
        return ret


class Integrator(models.Model):
    METHOD = (('TO', 'TOKEN'),
              ('DI', 'DIRECT'),
              ('EX', 'EXTERNAL'))

    name    = models.CharField(max_length=32)
    country = models.ForeignKey(Country)
    method  = models.CharField(max_length=2, choices=METHOD, default='TO')

    def __unicode__(self):
        return "%s_%s" % (self.name, self.country.code)
    
    @classmethod
    def get(cls, name):
        try:
            return cls.objects.get(name=name)
        except Exception:
            return None


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
            v = cls.objects.get(integrator=integrator, key=key)
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
    expiration        = models.DateField(blank=True, null=True, help_text="Expiration date")
    creation_date     = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True, blank=True, null=True)

    @property
    def is_active(self):
        if self.expiration is None:
            return False
        else:
            return self.expiration > date.today()

    def natural_key(self):
        return (self.user_id)

    def __unicode__(self):
        return self.user_id
        
    @classmethod
    def create(cls, user_id, email, country):
        us            = cls()
        us.user_id    = user_id
        us.email      = email
        us.country    = country
        us.save()
        return us
    
    def get_card(self):
        try:
            card = Card.objects.get(user=self, enabled=True)
        except ObjectDoesNotExist:
            return None
        except MultipleObjectsReturned:
            return None
        return card
    
    def add_to_expiration(self, days):
        ty, tm, td = timezone.now().strftime("%Y-%m-%d").split("-")
        # Obtengo cantidad de meses a sumar
        md = int(days / 30)
        # Sumo los meses
        m = int(tm) + md
        # Obtengo el mes resultante y los anios a sumar
        yd, month = divmod(m, 12)
        if month == 0:
            month = m - 12 * (yd - 1)
            year = int(ty) + yd - 1
        else:
            year = int(ty) + yd
        # Sumo los anio
        self.expiration = datetime(year, month, int(td))
        self.save()
        return self.expiration

    def set_expiration(self, date):
        self.expiration = date + timedelta(days=1)
        self.save()
        return self.expiration
        
    def enable_for(self, days):
        self.expiration = timezone.now() + timedelta(days=int(days))
        self.save()
        return self.expiration

    def enable_for(self, days):
        self.expiration = timezone.now() + timedelta(days=int(days))
        self.save()
        return self.expiration

    def expire(self):
        if self.expiration is not None:
            self.expiration = timezone.now()
            self.save()

    def has_expired(self):
        if self.expiration is not None:
            if self.expiration < timezone.now():
                return True
        return False
    
    def has_active_recurrence(self):
        ups = UserPayment.objects.filter(user=self, status='AC')
        if len(ups) > 0:
            return True
        else:
            return False

    def has_recurrence(self):
        ups = UserPayment.objects.filter(user=self)
        if len(ups) > 0:
            return True
        else:
            return False


class UserPayment(models.Model):
    STATUS = (('PE', 'Pending'),
              ('AC', 'Active'),
              ('CA', 'Cancelled'),
              ('ER', 'Error'),
              ('RE', 'Recurring Error'))

    CHANNEL = (('E', ''),
               ('U', 'User'),
               ('R', 'Reply'),
               ('C', 'Callback'),
               ('T', 'Timeout'),
               ('F', 'Refund'),
               ('X', 'Claxson'))

    user_payment_id   = models.CharField(max_length=128)
    user              = models.ForeignKey(User)
    amount            = models.FloatField(default=0)
    currency          = models.ForeignKey(Currency, blank=True, null=True)
    payment_date      = models.DateField(auto_now_add=False, blank=True, null=True, help_text='Next payment date')
    payday            = models.IntegerField(help_text='Payday number', blank=True, null=True)
    recurrence        = models.IntegerField(help_text="Daily recurrence")
    disc_pct          = models.IntegerField(default=0, help_text="Discount percentage")
    disc_counter      = models.IntegerField(default=0, help_text="Payments with discount remaining")
    status            = models.CharField(max_length=2, choices=STATUS, default='PE', help_text='Payment status')
    channel           = models.CharField(max_length=1, choices=CHANNEL, default='E', help_text='Error or cancellation channel')
    message           = models.CharField(max_length=1024, blank=True)
    retries           = models.IntegerField(default=0, help_text='Payment retries')
    internal          = models.BooleanField(default=True)
    enabled           = models.BooleanField(default=True)
    creation_date     = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __unicode__(self):
        return self.user_payment_id
    
    @classmethod
    def create(cls, user, recurrence, amount=0, currency=None, payment_date=0, payday=0, discount=0, disc_counter=0, internal=False):
        up = cls()
        up.user_payment_id = "UP_%s_%d" % (user.user_id, int(time.time()))
        up.user            = user
        up.amount          = float(amount)
        up.currency        = currency
        if payment_date == 0 or payment_date == 0.0 or payment_date == '0':
            #np = timezone.now() + timezone.timedelta(days=int(recurrence))
            #if int(recurrence) >= 30:
            #    up.payment_date = datetime(np.year,np.month,payday)
            #else:
            #    up.payment_date = datetime(np.year,np.month,np.day)
            up.payment_date = timezone.now()
            up.status       = 'PE'
        else:
            up.payment_date = datetime.fromtimestamp(int(payment_date))
            up.status       = 'AC'
        up.payday       = payday
        up.recurrence   = int(recurrence)
        up.disc_pct     = int(discount)
        up.disc_counter = int(disc_counter)
        up.internal     = internal
        up.enabled      = True
        up.save()
        return up
        
    @classmethod
    def get_by_id(cls, up_id):
        try:
            return cls.objects.get(user_payment_id=up_id)
        except ObjectDoesNotExist:
            return None
    
    def discount(self, discount, disc_counter):
        self.disc_pct     = discount
        self.disc_counter = disc_counter
        self.save()
        
    def disable(self):
        self.enabled = False
        self.save()

    def active(self):
        self.status  = 'AC'
        self.enabled = True
        self.save()
    
    def enable(self):
        self.enabled = True
        self.save()

    def error(self, channel, message=''):
        self.status = 'ER'
        self.message = message
        self.enabled = False
        self.channel = channel
        self.save()
    
    def reply_error(self, message=''):
        self.status  = 'ER'
        self.message = message
        self.enabled = False
        self.channel = 'R'
        self.save()

    def reply_recurrence_error(self, message=''):
        self.status  = 'RE'
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

    def cancel(self, channel, message=''):
        self.status  = 'CA'
        self.message = message
        self.enabled = False
        self.channel = channel
        self.save()

    def reply_cancel(self, message=''):
        self.status  = 'CA'
        self.message = message
        self.enabled = False
        self.channel = 'R'
        self.save()

    def user_cancel(self):
        self.enabled = False
        self.status  = 'CA'
        self.channel = 'U'
        self.save()

    def calculate_discount(self):
        if self.disc_counter > 0:
            return self.amount - (self.amount * float(self.disc_pct) / 100.0)
        else:
            return self.amount

    @staticmethod        
    def payday_calc(payment_date):
        day = payment_date.day
        if int(day) > 28:
            return 28
        else:
            return int(day)
        
            
    def calc_payment_date(self, date=None):
        if date is None:
            date = self.payment_date
        else:
            self.payday = self.payday_calc(date)
            self.save()            
        # Obtengo cantidad de meses a sumar
        md = int(int(self.recurrence) / 30)
        # Sumo los meses
        m = date.month + md
        # Obtengo el mes resultante y los anios a sumar
        yd, month = divmod(m, 12)
        if month == 0:
            month = m - 12 * (yd - 1)
            year = date.year + yd - 1
        else:
            year = date.year + yd
        # Sumo los anio
        self.payment_date = datetime(year, month, int(self.payday))
        #self.save()
        return self.payment_date
        
    def add_retry(self):
        self.retries = self.retries + 1
        self.save()
        return self


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
    deleted           = models.BooleanField(default=False)
    creation_date     = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __unicode__(self):
        return self.card_id
    
    @classmethod
    def create_with_token(cls, user, token, number, expiration, card_type, integrator):
        cd            = cls()
        cd.card_id    = "CD_%s_%d" % (user.user_id, int(time.time()))
        cd.user       = user
        cd.token      = token
        cd.number     = number
        cd.expiration = expiration
        cd.card_type  = card_type
        cd.integrator = integrator
        cd.enabled    = True
        cd.save()
        return cd
    
    def enable(self):
        self.deleted = False
        self.enabled = True
        self.save()
        
    def disable(self):
        self.enabled = False
        self.save()

    def sdelete(self):
        self.deleted = True
        self.save()


class PaymentHistory(models.Model):
    STATUS = (('P', 'Processing'),
              ('W', 'Waiting callback'),
              ('A', 'Approved'),
              ('R', 'Rejected'),
              ('C', 'Cancelled'),
              ('E', 'Error'))

    user_payment      = models.ForeignKey(UserPayment)
    card              = models.ForeignKey(Card, blank=True, null=True)
    status            = models.CharField(max_length=1, choices=STATUS, default='P')
    payment_id        = models.CharField(max_length=128, help_text='Internal ID')
    gateway_id        = models.CharField(max_length=128, blank=True, null=True, help_text='External ID')
    amount            = models.FloatField(help_text='amount=net_amount + tax_amount')
    vat_amount        = models.FloatField(default=0, help_text='Tax amount')
    taxable_amount    = models.FloatField(default=0, help_text='Net amount')
    disc_pct          = models.IntegerField(default=0, help_text="Discount percentage")
    message           = models.CharField(max_length=2048, blank=True)
    integrator        = models.ForeignKey(Integrator, blank=True, null=True)
    manual            = models.BooleanField(default=False, help_text='True if manual payment')
    creation_date     = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __unicode__(self):
        return self.payment_id

    def __amounts_calculator(self):
        amount = self.user_payment.calculate_discount()
        tax    = self.user_payment.user.country.tax

        if tax > 0:
            if self.user_payment.user.country.full_price:
                taxable_amount = round(amount / tax, 2)
                calc_amount    = amount
                vat_amount     = round(amount - taxable_amount, 2)
            else:
                taxable_amount = amount
                calc_amount    = round(taxable_amount * tax, 2)
                vat_amount     = round(amount - taxable_amount, 2)
        else:
            calc_amount    = amount
            taxable_amount = amount
            vat_amount     = 0

        return {'amount': calc_amount, 'taxable_amount': taxable_amount, 'vat_amount': vat_amount}

    @classmethod
    def get(cls, user_payment, status):
        try:
            return cls.objects.get(user_payment=user_payment, status=status)
        except Exception:
            return None

    @classmethod
    def create(cls, user_payment, payment_id, integrator, card=None, disc_pct=0, manual=False, gateway_id='', status='P'):
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
        ph.integrator     = integrator
        ph.manual         = manual
        ph.save()
        return ph

    def approve(self, gw_id, message=''):
        self.status     = 'A'
        self.gateway_id = gw_id
        self.message    = message
        self.save()

    def reject(self, gw_id, message=''):
        self.status     = 'R'
        self.gateway_id = gw_id
        self.message    = message
        self.save()

    def error(self, gw_id, message=''):
        self.status     = 'E'
        self.gateway_id = gw_id
        self.message    = message
        self.save()

    def cancel(self, gw_id, message=''):
        self.status     = 'C'
        self.gateway_id = gw_id
        self.message    = message
        self.save()

    def __unicode__(self):
        return "%s" % (self.payment_id)


class Package(models.Model):
    package_id = models.CharField(max_length=10)
    duration   = models.IntegerField()
    amount     = models.FloatField()
    integrator = models.ForeignKey(Integrator)

    @classmethod
    def get(cls, duration, integrator):
        try:
            return cls.objects.get(duration=duration, integrator=integrator)
        except Exception:
            return None

    @classmethod
    def get_var(cls, duration, key):
        try:
            v = cls.objects.get(duration=duration, key=key)
            if cast:
                return v.cast()
            else:
                return v
        except ObjectDoesNotExist:
            return None

    def __unicode__(self):
        return self.package_id
