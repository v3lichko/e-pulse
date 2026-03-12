from decimal import Decimal

from rest_framework import serializers

from apps.stations.models import Connector
from .models import Booking

BOOKING_FEE = Decimal('50.00')


class CreateBookingSerializer(serializers.Serializer):
    connector_id = serializers.IntegerField()

    def validate_connector_id(self, value):
        try:
            connector = Connector.objects.select_related('station').get(pk=value)
        except Connector.DoesNotExist:
            raise serializers.ValidationError('Разъём не найден')

        if connector.status != Connector.StatusChoices.FREE:
            raise serializers.ValidationError(
                f'Разъём недоступен для бронирования (статус: {connector.get_status_display()})'
            )

        return value

    def validate(self, attrs):
        connector_id = attrs['connector_id']
        user = self.context['request'].user

        try:
            connector = Connector.objects.select_related('station').get(pk=connector_id)
        except Connector.DoesNotExist:
            raise serializers.ValidationError('Разъём не найден')

        # Check if user already has active booking for this station
        existing_booking = Booking.objects.filter(
            user=user,
            connector__station=connector.station,
            status=Booking.StatusChoices.ACTIVE,
        ).first()

        if existing_booking:
            raise serializers.ValidationError(
                'У вас уже есть активная бронь на этой станции'
            )

        attrs['connector'] = connector
        attrs['booking_fee'] = BOOKING_FEE
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        connector = validated_data['connector']
        booking_fee = validated_data['booking_fee']

        booking = Booking(
            user=user,
            connector=connector,
            booking_fee=booking_fee,
        )
        booking.save()
        return booking


class BookingSerializer(serializers.ModelSerializer):
    station_name = serializers.SerializerMethodField()
    station_address = serializers.SerializerMethodField()
    connector_type = serializers.SerializerMethodField()
    connector_power_kw = serializers.SerializerMethodField()
    is_expired = serializers.ReadOnlyField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    minutes_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'id',
            'connector',
            'created_at',
            'expires_at',
            'booking_fee',
            'status',
            'status_display',
            'is_expired',
            'station_name',
            'station_address',
            'connector_type',
            'connector_power_kw',
            'minutes_remaining',
        ]
        read_only_fields = ['id', 'created_at', 'expires_at', 'booking_fee', 'status']

    def get_station_name(self, obj):
        return obj.connector.station.name

    def get_station_address(self, obj):
        return obj.connector.station.address

    def get_connector_type(self, obj):
        return obj.connector.connector_type

    def get_connector_power_kw(self, obj):
        return float(obj.connector.power_kw)

    def get_minutes_remaining(self, obj):
        from django.utils import timezone
        if obj.status != Booking.StatusChoices.ACTIVE:
            return 0
        remaining = (obj.expires_at - timezone.now()).total_seconds()
        return max(0, int(remaining / 60))
