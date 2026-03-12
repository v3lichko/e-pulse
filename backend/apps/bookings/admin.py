from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'connector', 'created_at', 'expires_at',
        'booking_fee', 'status'
    ]
    list_filter = ['status']
    search_fields = ['user__phone', 'connector__station__name']
    ordering = ['-created_at']
    readonly_fields = ['created_at']

    fieldsets = (
        ('Участники', {'fields': ('user', 'connector')}),
        ('Данные брони', {
            'fields': ('created_at', 'expires_at', 'booking_fee', 'status')
        }),
    )
