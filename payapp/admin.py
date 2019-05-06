from django.contrib import admin
import models

# Register your models here.

@admin.register(models.Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'dtype']

@admin.register(models.Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']

@admin.register(models.User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['user_id', 'email', 'country', 'expiration', 'creation_date']

@admin.register(models.Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'currency', 'tax', 'full_price']

@admin.register(models.Integrator)
class IntegratorAdmin(admin.ModelAdmin):
    list_display = ['name', 'country']

@admin.register(models.IntegratorSetting)
class IntegratorSettingAdmin(admin.ModelAdmin):
    list_display = ['integrator', 'key', 'value', 'dtype']

@admin.register(models.UserPayment)
class UserPaymentAdmin(admin.ModelAdmin):
    list_display = ['user_payment_id', 'user', 'amount', 'currency', 'payment_date', 'recurrence', 'status', 'enabled', 'creation_date', 'message']

@admin.register(models.Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ['card_id', 'user', 'token', 'integrator', 'enabled', 'deleted', 'creation_date']

@admin.register(models.PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = ['payment_id', 'user_payment', 'status', 'card', 'gateway_id', 'amount',
                    'taxable_amount', 'vat_amount', 'creation_date', 'modification_date']

@admin.register(models.Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ['package_id', 'duration', 'amount', 'integrator']
