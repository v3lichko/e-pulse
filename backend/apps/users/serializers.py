from rest_framework import serializers
from phonenumber_field.serializerfields import PhoneNumberField
from .models import User, OTPCode, FavoriteStation


class SendOTPSerializer(serializers.Serializer):
    phone = PhoneNumberField()

    def validate_phone(self, value):
        return value


class VerifyOTPSerializer(serializers.Serializer):
    phone = PhoneNumberField()
    code = serializers.CharField(max_length=6, min_length=6)


class UserSerializer(serializers.ModelSerializer):
    phone = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'phone', 'name', 'date_joined']
        read_only_fields = ['id', 'phone', 'date_joined']

    def get_phone(self, obj):
        return str(obj.phone)


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['name']


class FavoriteStationSerializer(serializers.ModelSerializer):
    station = serializers.SerializerMethodField()

    class Meta:
        model = FavoriteStation
        fields = ['id', 'station', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_station(self, obj):
        from apps.stations.serializers import StationListSerializer
        return StationListSerializer(obj.station, context=self.context).data
