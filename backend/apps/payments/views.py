import logging
from decimal import Decimal

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Wallet, WalletTransaction
from .serializers import (
    WalletSerializer,
    TopUpSerializer,
    WalletTransactionSerializer,
    QRPaymentSerializer,
)

logger = logging.getLogger(__name__)


class WalletView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WalletSerializer

    def get_object(self):
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        return wallet


class TopUpInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TopUpSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response({
            'deeplink_url': result['deeplink_url'],
            'amount': result['amount'],
            'message': 'Перейдите по ссылке для оплаты в банковском приложении',
        })


class TopUpCallbackView(APIView):
    """
    Webhook endpoint called by bank after successful payment.
    In production, this should be secured with bank signature verification.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        user_id = request.data.get('user_id')
        amount = request.data.get('amount')
        transaction_ref = request.data.get('transaction_ref', '')
        success = request.data.get('success', False)

        if not success:
            return Response(
                {'error': 'Платёж не успешен'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user_id or not amount:
            return Response(
                {'error': 'Отсутствуют обязательные параметры'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from apps.users.models import User
            user = User.objects.get(pk=user_id)
            wallet, _ = Wallet.objects.get_or_create(user=user)

            amount = Decimal(str(amount))
            wallet.balance += amount
            wallet.save()

            WalletTransaction.objects.create(
                wallet=wallet,
                amount=amount,
                transaction_type=WalletTransaction.TypeChoices.TOPUP,
                description=f'Пополнение кошелька. Реф: {transaction_ref}',
            )

            logger.info(f'Wallet topped up: user={user_id}, amount={amount}')
            return Response({'message': 'Кошелёк пополнен', 'balance': wallet.balance})

        except Exception as e:
            logger.error(f'Error processing topup callback: {e}')
            return Response(
                {'error': 'Ошибка обработки платежа'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class WalletTransactionListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WalletTransactionSerializer

    def get_queryset(self):
        return WalletTransaction.objects.filter(
            wallet__user=self.request.user
        ).order_by('-created_at')


class QRPaymentInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = QRPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        connector_id = serializer.validated_data['connector_id']
        amount = serializer.validated_data['amount']

        # Generate QR payment URL (stub implementation)
        # In production, integrate with payment provider (e.g., Sberbank, Tinkoff)
        import uuid
        payment_id = uuid.uuid4().hex

        qr_url = (
            f'https://payment.example.com/qr/{payment_id}'
            f'?connector_id={connector_id}&amount={amount}'
        )

        return Response({
            'qr_url': qr_url,
            'payment_id': payment_id,
            'amount': amount,
            'connector_id': connector_id,
            'message': 'Отсканируйте QR-код для оплаты',
        })
