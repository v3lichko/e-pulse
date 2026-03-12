from django.contrib import admin
from .models import PushToken, Notification


@admin.register(PushToken)
class PushTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'platform', 'created_at', 'updated_at']
    list_filter = ['platform']
    search_fields = ['user__phone', 'token']
    ordering = ['-updated_at']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'title', 'notification_type', 'is_read', 'created_at'
    ]
    list_filter = ['notification_type', 'is_read']
    search_fields = ['user__phone', 'title', 'body']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
