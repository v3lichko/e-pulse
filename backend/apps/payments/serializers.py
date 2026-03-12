from decimal import Decimal

from rest_framework import serializers

from .models import Wallet, WalletTransaction


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['balance', 'updated_at']
        read_only_fields = ['balance', 'updated_at']


class TopUpSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_amount(self, value):
        if value < Decimal('100'):
            raise serializers.ValidationError('Минимальная сумма пополнения: 100₽')
        if value > Decimal('100000'):
            raise serializers.ValidationError('Максимальная сумма пополнения: 100000₽')
        return value

    def create(self, validated_data):
        amount = validated_data['amount']
        user = self.context['request'].user

        # Generate deeplink URL for bank app (stub implementation)
        return_url = 'evapp://wallet/callback'
        deeplink_url = (
            f'bank://topup?amount={amount}'
            f'&return_url={return_url}'
            f'&user_id={user.pk}'
            f'&description=Пополнение+кошелька+EV+Charging'
        )

        return {
            'deeplink_url': deeplink_url,
            'amount': amount,
        }


class WalletTransactionSerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.CharField(
        source='get_transaction_type_display', read_only=True
    )
    is_credit = serializers.SerializerMethodField()

    class Meta:
        model = WalletTransaction
        fields = [
            'id',
            'amount',
            'transaction_type',
            'transaction_type_display',
            'description',
            'session',
            'booking',
            'created_at',
            'is_credit',
        ]
        read_only_fields = ['id', 'created_at']

    def get_is_credit(self, obj):
        return obj.amount > 0


class QRPaymentSerializer(serializers.Serializer):
    connector_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Сумма должна быть положительной')
        return value

    def validate_connector_id(self, value):
        from apps.stations.models import Connector
        try:
            Connector.objects.get(pk=value)
        except Connector.DoesNotExist:
            raise serializers.ValidationError('Разъём не найден')
        return value
