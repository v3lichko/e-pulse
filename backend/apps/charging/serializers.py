from rest_framework import serializers
from .models import ChargingSession, Receipt


class ChargingSessionSerializer(serializers.ModelSerializer):
    station_name = serializers.SerializerMethodField()
    station_address = serializers.SerializerMethodField()
    connector_type = serializers.SerializerMethodField()
    duration_seconds = serializers.ReadOnlyField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(
        source='get_payment_method_display', read_only=True
    )

    class Meta:
        model = ChargingSession
        fields = [
            'id',
            'user',
            'connector',
            'booking',
            'start_time',
            'end_time',
            'energy_kwh',
            'cost',
            'current_power_kw',
            'payment_method',
            'payment_method_display',
            'status',
            'status_display',
            'transaction_id',
            'ocpp_transaction_id',
            'created_at',
            'duration_seconds',
            'station_name',
            'station_address',
            'connector_type',
        ]
        read_only_fields = [
            'id', 'user', 'start_time', 'end_time', 'energy_kwh',
            'cost', 'current_power_kw', 'status', 'created_at'
        ]

    def get_station_name(self, obj):
        return obj.connector.station.name

    def get_station_address(self, obj):
        return obj.connector.station.address

    def get_connector_type(self, obj):
        return obj.connector.connector_type


class StartChargingSerializer(serializers.Serializer):
    connector_id = serializers.IntegerField()
    payment_method = serializers.ChoiceField(
        choices=ChargingSession.PaymentMethodChoices.choices
    )
    qr_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )


class StopChargingSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()


class ActiveSessionSerializer(serializers.ModelSerializer):
    station_name = serializers.SerializerMethodField()
    station_address = serializers.SerializerMethodField()
    connector_type = serializers.SerializerMethodField()
    duration_seconds = serializers.ReadOnlyField()
    price_per_kwh = serializers.SerializerMethodField()
    estimated_cost = serializers.SerializerMethodField()

    class Meta:
        model = ChargingSession
        fields = [
            'id',
            'connector',
            'start_time',
            'energy_kwh',
            'cost',
            'current_power_kw',
            'payment_method',
            'status',
            'duration_seconds',
            'station_name',
            'station_address',
            'connector_type',
            'price_per_kwh',
            'estimated_cost',
        ]

    def get_station_name(self, obj):
        return obj.connector.station.name

    def get_station_address(self, obj):
        return obj.connector.station.address

    def get_connector_type(self, obj):
        return obj.connector.connector_type

    def get_price_per_kwh(self, obj):
        return float(obj.connector.price_per_kwh)

    def get_estimated_cost(self, obj):
        return float(obj.energy_kwh) * float(obj.connector.price_per_kwh)


class ReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipt
        fields = [
            'id',
            'session',
            'station_name',
            'station_address',
            'connector_type',
            'energy_kwh',
            'cost',
            'payment_method',
            'start_time',
            'end_time',
            'receipt_number',
            'created_at',
        ]
