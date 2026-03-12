from rest_framework import serializers
from haversine import haversine, Unit
from .models import Station, Connector


class ConnectorSerializer(serializers.ModelSerializer):
    connector_type_display = serializers.CharField(
        source='get_connector_type_display', read_only=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Connector
        fields = [
            'id',
            'connector_type',
            'connector_type_display',
            'power_kw',
            'price_per_kwh',
            'status',
            'status_display',
            'connector_number',
            'image',
            'ocpp_connector_id',
        ]


class StationListSerializer(serializers.ModelSerializer):
    connectors = ConnectorSerializer(many=True, read_only=True)
    status = serializers.ReadOnlyField()
    distance = serializers.SerializerMethodField()

    class Meta:
        model = Station
        fields = [
            'id',
            'name',
            'address',
            'latitude',
            'longitude',
            'status',
            'connectors',
            'distance',
        ]

    def get_distance(self, obj):
        request = self.context.get('request')
        lat = self.context.get('lat')
        lng = self.context.get('lng')

        if request and not (lat and lng):
            lat = request.query_params.get('lat')
            lng = request.query_params.get('lng')

        if lat and lng:
            try:
                user_location = (float(lat), float(lng))
                station_location = (float(obj.latitude), float(obj.longitude))
                distance_km = haversine(user_location, station_location, unit=Unit.KILOMETERS)
                return round(distance_km, 2)
            except (ValueError, TypeError):
                return None
        return None


class StationDetailSerializer(StationListSerializer):
    class Meta(StationListSerializer.Meta):
        fields = StationListSerializer.Meta.fields + [
            'image',
            'description',
            'working_hours',
            'is_active',
            'created_at',
            'updated_at',
        ]


class StationAdminSerializer(serializers.ModelSerializer):
    connectors = ConnectorSerializer(many=True, read_only=True)
    status = serializers.ReadOnlyField()

    class Meta:
        model = Station
        fields = '__all__'
