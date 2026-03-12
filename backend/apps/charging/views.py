import logging
from decimal import Decimal

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.stations.models import Connector
from .models import ChargingSession, Receipt
from .serializers import (
    ChargingSessionSerializer,
    StartChargingSerializer,
    StopChargingSerializer,
    ActiveSessionSerializer,
    ReceiptSerializer,
)

logger = logging.getLogger(__name__)


class StartChargingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StartChargingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        connector_id = serializer.validated_data['connector_id']
        payment_method = serializer.validated_data['payment_method']
        qr_amount = serializer.validated_data.get('qr_amount')

        try:
            connector = Connector.objects.select_related('station').get(pk=connector_id)
        except Connector.DoesNotExist:
            return Response(
                {'error': 'Разъём не найден'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if user already has active session
        existing_session = ChargingSession.objects.filter(
            user=request.user,
            status=ChargingSession.StatusChoices.ACTIVE
        ).first()
        if existing_session:
            return Response(
                {'error': 'У вас уже есть активная сессия зарядки'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check connector availability
        booking = None
        if connector.status == Connector.StatusChoices.RESERVED:
            # Check if user has a valid booking for this connector
            from apps.bookings.models import Booking
            booking = Booking.objects.filter(
                user=request.user,
                connector=connector,
                status=Booking.StatusChoices.ACTIVE
            ).first()
            if not booking:
                return Response(
                    {'error': 'Разъём забронирован другим пользователем'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif connector.status != Connector.StatusChoices.FREE:
            return Response(
                {'error': f'Разъём недоступен (статус: {connector.get_status_display()})'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Wallet payment validation
        if payment_method == ChargingSession.PaymentMethodChoices.WALLET:
            try:
                wallet = request.user.wallet
            except Exception:
                return Response(
                    {'error': 'Кошелёк не найден'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            min_balance = connector.price_per_kwh * Decimal('5')
            if wallet.balance < min_balance:
                return Response(
                    {'error': f'Недостаточно средств. Минимальный баланс: {min_balance}₽'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Create charging session
        session = ChargingSession.objects.create(
            user=request.user,
            connector=connector,
            booking=booking,
            payment_method=payment_method,
            status=ChargingSession.StatusChoices.ACTIVE,
        )

        # Update connector status
        connector.status = Connector.StatusChoices.BUSY
        connector.save()

        # Mark booking as used if exists
        if booking:
            booking.status = 'used'
            booking.save()

        # Send push notification
        try:
            from apps.notifications.services import NotificationService
            NotificationService.send_charging_started(request.user, session)
        except Exception as e:
            logger.warning(f'Failed to send push notification: {e}')

        return Response(
            ChargingSessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )


class StopChargingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StopChargingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data['session_id']

        try:
            session = ChargingSession.objects.select_related(
                'connector__station', 'user'
            ).get(
                pk=session_id,
                user=request.user,
                status=ChargingSession.StatusChoices.ACTIVE,
            )
        except ChargingSession.DoesNotExist:
            return Response(
                {'error': 'Активная сессия не найдена'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Calculate final cost
        final_cost = session.energy_kwh * session.connector.price_per_kwh

        # Deduct from wallet if payment is wallet
        if session.payment_method == ChargingSession.PaymentMethodChoices.WALLET:
            try:
                wallet = request.user.wallet
                if wallet.balance >= final_cost:
                    wallet.balance -= final_cost
                    wallet.save()

                    from apps.payments.models import WalletTransaction
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=-final_cost,
                        transaction_type=WalletTransaction.TypeChoices.CHARGE,
                        description=f'Оплата зарядки #{session.pk}',
                        session=session,
                    )
                else:
                    # Charge whatever is available
                    final_cost = wallet.balance
                    wallet.balance = Decimal('0')
                    wallet.save()

                    from apps.payments.models import WalletTransaction
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=-final_cost,
                        transaction_type=WalletTransaction.TypeChoices.CHARGE,
                        description=f'Оплата зарядки #{session.pk} (частичная)',
                        session=session,
                    )
            except Exception as e:
                logger.error(f'Error processing wallet payment: {e}')

        # Finalize session
        session.end_time = timezone.now()
        session.cost = final_cost
        session.status = ChargingSession.StatusChoices.COMPLETED
        session.save()

        # Free connector
        connector = session.connector
        connector.status = Connector.StatusChoices.FREE
        connector.save()

        # Create receipt
        receipt = Receipt.objects.create(
            session=session,
            station_name=connector.station.name,
            station_address=connector.station.address,
            connector_type=connector.connector_type,
            energy_kwh=session.energy_kwh,
            cost=session.cost,
            payment_method=session.payment_method,
            start_time=session.start_time,
            end_time=session.end_time,
            receipt_number=Receipt.generate_receipt_number(),
        )

        # Send push notification
        try:
            from apps.notifications.services import NotificationService
            NotificationService.send_charging_completed(request.user, session, receipt)
        except Exception as e:
            logger.warning(f'Failed to send push notification: {e}')

        return Response({
            'session': ChargingSessionSerializer(session).data,
            'receipt': ReceiptSerializer(receipt).data,
        })


class ActiveSessionView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ActiveSessionSerializer

    def get_object(self):
        session = ChargingSession.objects.filter(
            user=self.request.user,
            status=ChargingSession.StatusChoices.ACTIVE,
        ).select_related('connector__station').first()

        if not session:
            from rest_framework.exceptions import NotFound
            raise NotFound('Нет активной сессии зарядки')

        return session


class ChargingHistoryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChargingSessionSerializer

    def get_queryset(self):
        return ChargingSession.objects.filter(
            user=self.request.user,
            status=ChargingSession.StatusChoices.COMPLETED,
        ).select_related('connector__station').order_by('-start_time')


class ReceiptView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReceiptSerializer

    def get_object(self):
        session_id = self.kwargs['session_id']
        try:
            receipt = Receipt.objects.get(
                session_id=session_id,
                session__user=self.request.user,
            )
        except Receipt.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Чек не найден')
        return receipt
