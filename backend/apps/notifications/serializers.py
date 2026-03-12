from rest_framework import serializers
from .models import PushToken, Notification


class PushTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushToken
        fields = ['id', 'token', 'platform', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class NotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', read_only=True
    )

    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'body',
            'notification_type',
            'notification_type_display',
            'data',
            'is_read',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
