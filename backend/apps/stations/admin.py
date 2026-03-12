from django.contrib import admin
from .models import Station, Connector


class ConnectorInline(admin.TabularInline):
    model = Connector
    extra = 1
    fields = [
        'connector_number', 'connector_type', 'power_kw',
        'price_per_kwh', 'status', 'ocpp_connector_id'
    ]


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'status', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'address']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ConnectorInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'address', 'description', 'image', 'working_hours')
        }),
        ('Координаты', {
            'fields': ('latitude', 'longitude')
        }),
        ('Настройки', {
            'fields': ('is_active',)
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Connector)
class ConnectorAdmin(admin.ModelAdmin):
    list_display = [
        'station', 'connector_number', 'connector_type',
        'power_kw', 'price_per_kwh', 'status'
    ]
    list_filter = ['connector_type', 'status']
    search_fields = ['station__name']
    ordering = ['station', 'connector_number']
