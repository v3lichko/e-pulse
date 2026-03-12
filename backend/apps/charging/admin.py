from django.contrib import admin
from .models import ChargingSession, Receipt


@admin.register(ChargingSession)
class ChargingSessionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'connector', 'start_time', 'end_time',
        'energy_kwh', 'cost', 'payment_method', 'status'
    ]
    list_filter = ['status', 'payment_method']
    search_fields = ['user__phone', 'connector__station__name']
    ordering = ['-start_time']
    readonly_fields = ['start_time', 'created_at']

    fieldsets = (
        ('Участники', {'fields': ('user', 'connector', 'booking')}),
        ('Данные сессии', {
            'fields': (
                'start_time', 'end_time', 'energy_kwh', 'cost',
                'current_power_kw', 'payment_method', 'status'
            )
        }),
        ('OCPP', {
            'fields': ('transaction_id', 'ocpp_transaction_id'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = [
        'receipt_number', 'session', 'station_name', 'energy_kwh',
        'cost', 'payment_method', 'created_at'
    ]
    search_fields = ['receipt_number', 'station_name', 'session__user__phone']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'receipt_number']
