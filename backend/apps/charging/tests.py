from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.bookings.models import Booking
from apps.charging.models import ChargingSession, Receipt
from apps.notifications.models import Notification
from apps.payments.models import Wallet
from apps.stations.models import Station, Connector
from apps.users.models import User


class ChargingTestBase(APITestCase):
    """Base class with common setUp for all charging tests."""

    def setUp(self):
        self.user = User.objects.create_user(phone='+79991234567')
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        self.station = Station.objects.create(
            name='Test', address='addr', latitude=55.75, longitude=37.62
        )
        self.connector = Connector.objects.create(
            station=self.station,
            connector_type='type2',
            power_kw=22,
            price_per_kwh='8.50',
            status='free',
            connector_number=1,
        )
        self.wallet, _ = Wallet.objects.get_or_create(user=self.user, defaults={'balance': 500})
        if not _:
            self.wallet.balance = 500
            self.wallet.save()


# ---------------------------------------------------------------------------
# Start Charging Tests
# ---------------------------------------------------------------------------
class StartChargingTests(ChargingTestBase):

    def test_start_charging_wallet(self):
        """POST /api/v1/charging/start/ with wallet payment creates session and marks connector busy."""
        response = self.client.post('/api/v1/charging/start/', {
            'connector_id': self.connector.pk,
            'payment_method': 'wallet',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        session = ChargingSession.objects.get(user=self.user)
        self.assertEqual(session.status, ChargingSession.StatusChoices.ACTIVE)
        self.assertEqual(session.payment_method, ChargingSession.PaymentMethodChoices.WALLET)

        self.connector.refresh_from_db()
        self.assertEqual(self.connector.status, Connector.StatusChoices.BUSY)

    def test_start_charging_connector_not_found(self):
        """Invalid connector_id returns 404."""
        response = self.client.post('/api/v1/charging/start/', {
            'connector_id': 99999,
            'payment_method': 'wallet',
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_start_charging_connector_busy(self):
        """Busy connector returns 400."""
        self.connector.status = Connector.StatusChoices.BUSY
        self.connector.save()

        response = self.client.post('/api/v1/charging/start/', {
            'connector_id': self.connector.pk,
            'payment_method': 'wallet',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_charging_already_active_session(self):
        """Starting a second session while one is active returns 400."""
        # First session succeeds
        self.client.post('/api/v1/charging/start/', {
            'connector_id': self.connector.pk,
            'payment_method': 'wallet',
        })

        # Create another free connector for the second attempt
        connector2 = Connector.objects.create(
            station=self.station,
            connector_type='type2',
            power_kw=22,
            price_per_kwh='8.50',
            status='free',
            connector_number=2,
        )

        response = self.client.post('/api/v1/charging/start/', {
            'connector_id': connector2.pk,
            'payment_method': 'wallet',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_charging_wallet_insufficient(self):
        """Wallet balance of 0 returns 400 (insufficient funds)."""
        self.wallet.balance = Decimal('0')
        self.wallet.save()

        response = self.client.post('/api/v1/charging/start/', {
            'connector_id': self.connector.pk,
            'payment_method': 'wallet',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_charging_with_booking(self):
        """
        If connector is reserved and user has an active booking,
        charging starts and booking becomes 'used'.
        """
        self.connector.status = Connector.StatusChoices.RESERVED
        self.connector.save()

        booking = Booking.objects.create(
            user=self.user,
            connector=self.connector,
            booking_fee=50,
            expires_at=timezone.now() + timedelta(minutes=20),
        )
        # Booking.save() sets connector to reserved, refresh to be safe
        self.connector.refresh_from_db()

        response = self.client.post('/api/v1/charging/start/', {
            'connector_id': self.connector.pk,
            'payment_method': 'wallet',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        booking.refresh_from_db()
        self.assertEqual(booking.status, 'used')

        session = ChargingSession.objects.get(user=self.user)
        self.assertEqual(session.booking_id, booking.pk)

    def test_start_charging_reserved_no_booking(self):
        """Connector reserved but user has no booking returns 400."""
        self.connector.status = Connector.StatusChoices.RESERVED
        self.connector.save()

        response = self.client.post('/api/v1/charging/start/', {
            'connector_id': self.connector.pk,
            'payment_method': 'wallet',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Stop Charging Tests
# ---------------------------------------------------------------------------
class StopChargingTests(ChargingTestBase):

    def _start_session(self):
        """Helper: start a charging session and return it."""
        response = self.client.post('/api/v1/charging/start/', {
            'connector_id': self.connector.pk,
            'payment_method': 'wallet',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return ChargingSession.objects.get(user=self.user, status='active')

    def test_stop_charging(self):
        """POST /api/v1/charging/stop/ completes session, frees connector, creates receipt."""
        session = self._start_session()

        response = self.client.post('/api/v1/charging/stop/', {
            'session_id': session.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        session.refresh_from_db()
        self.assertEqual(session.status, ChargingSession.StatusChoices.COMPLETED)
        self.assertIsNotNone(session.end_time)

        self.connector.refresh_from_db()
        self.assertEqual(self.connector.status, Connector.StatusChoices.FREE)

        self.assertTrue(Receipt.objects.filter(session=session).exists())

    def test_stop_charging_wallet_deduction(self):
        """Stopping a session with 10 kWh deducts 10 * 8.50 = 85 from wallet."""
        session = self._start_session()

        session.energy_kwh = Decimal('10')
        session.save(update_fields=['energy_kwh'])

        response = self.client.post('/api/v1/charging/stop/', {
            'session_id': session.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('500') - Decimal('85'))

        session.refresh_from_db()
        self.assertEqual(session.cost, Decimal('85.00'))

    def test_stop_charging_wrong_session(self):
        """Wrong session_id returns 404."""
        response = self.client.post('/api/v1/charging/stop/', {
            'session_id': 99999,
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_stop_charging_unauthenticated(self):
        """Unauthenticated request returns 401."""
        self.client.credentials()  # remove auth
        response = self.client.post('/api/v1/charging/stop/', {
            'session_id': 1,
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Active Session Tests
# ---------------------------------------------------------------------------
class ActiveSessionTests(ChargingTestBase):

    def test_active_session(self):
        """GET /api/v1/charging/active/ returns the active session."""
        self.client.post('/api/v1/charging/start/', {
            'connector_id': self.connector.pk,
            'payment_method': 'wallet',
        })

        response = self.client.get('/api/v1/charging/active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'active')
        self.assertIn('station_name', response.data)
        self.assertIn('price_per_kwh', response.data)

    def test_no_active_session(self):
        """GET /api/v1/charging/active/ with no active session returns 404."""
        response = self.client.get('/api/v1/charging/active/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# History Tests
# ---------------------------------------------------------------------------
class ChargingHistoryTests(ChargingTestBase):

    def test_charging_history(self):
        """GET /api/v1/charging/history/ returns completed sessions."""
        session = ChargingSession.objects.create(
            user=self.user,
            connector=self.connector,
            payment_method='wallet',
            status=ChargingSession.StatusChoices.COMPLETED,
            energy_kwh=Decimal('5.000'),
            cost=Decimal('42.50'),
            end_time=timezone.now(),
        )

        response = self.client.get('/api/v1/charging/history/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], session.pk)

    def test_charging_history_empty(self):
        """GET /api/v1/charging/history/ with no sessions returns empty list."""
        response = self.client.get('/api/v1/charging/history/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)


# ---------------------------------------------------------------------------
# Receipt Tests
# ---------------------------------------------------------------------------
class ReceiptTests(ChargingTestBase):

    def _create_completed_session_with_receipt(self):
        """Helper: create a completed session with receipt."""
        session = ChargingSession.objects.create(
            user=self.user,
            connector=self.connector,
            payment_method='wallet',
            status=ChargingSession.StatusChoices.COMPLETED,
            energy_kwh=Decimal('5.000'),
            cost=Decimal('42.50'),
            end_time=timezone.now(),
        )
        receipt = Receipt.objects.create(
            session=session,
            station_name=self.station.name,
            station_address=self.station.address,
            connector_type=self.connector.connector_type,
            energy_kwh=session.energy_kwh,
            cost=session.cost,
            payment_method=session.payment_method,
            start_time=session.start_time,
            end_time=session.end_time,
            receipt_number=Receipt.generate_receipt_number(),
        )
        return session, receipt

    def test_get_receipt(self):
        """GET /api/v1/charging/{session_id}/receipt/ returns receipt data."""
        session, receipt = self._create_completed_session_with_receipt()

        response = self.client.get(f'/api/v1/charging/{session.pk}/receipt/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['receipt_number'], receipt.receipt_number)
        self.assertEqual(response.data['station_name'], 'Test')

    def test_receipt_not_found(self):
        """GET /api/v1/charging/{session_id}/receipt/ with no receipt returns 404."""
        response = self.client.get('/api/v1/charging/99999/receipt/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Notification Tests
# ---------------------------------------------------------------------------
class NotificationTests(ChargingTestBase):

    def test_start_sends_notification(self):
        """Starting a charging session creates a charging_start Notification."""
        response = self.client.post('/api/v1/charging/start/', {
            'connector_id': self.connector.pk,
            'payment_method': 'wallet',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        notifications = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.TypeChoices.CHARGING_START,
        )
        self.assertTrue(notifications.exists())

    def test_stop_sends_notification(self):
        """Stopping a charging session creates a charging_end Notification."""
        # Start session
        self.client.post('/api/v1/charging/start/', {
            'connector_id': self.connector.pk,
            'payment_method': 'wallet',
        })
        session = ChargingSession.objects.get(user=self.user, status='active')

        # Stop session
        response = self.client.post('/api/v1/charging/stop/', {
            'session_id': session.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        notifications = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.TypeChoices.CHARGING_END,
        )
        self.assertTrue(notifications.exists())
