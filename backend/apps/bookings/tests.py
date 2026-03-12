from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.bookings.models import Booking
from apps.bookings.tasks import expire_bookings
from apps.notifications.models import Notification
from apps.stations.models import Connector, Station
from apps.users.models import User


class BookingTestCase(APITestCase):
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

    def test_create_booking(self):
        response = self.client.post(
            '/api/v1/bookings/',
            {'connector_id': self.connector.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.connector.refresh_from_db()
        self.assertEqual(self.connector.status, Connector.StatusChoices.RESERVED)

        booking = Booking.objects.get(pk=response.data['id'])
        self.assertEqual(booking.booking_fee, Decimal('50.00'))
        self.assertEqual(booking.status, Booking.StatusChoices.ACTIVE)

        # expires_at should be approximately 20 minutes from now
        expected = timezone.now() + timedelta(minutes=20)
        diff = abs((booking.expires_at - expected).total_seconds())
        self.assertLess(diff, 10)

    def test_create_booking_connector_busy(self):
        self.connector.status = Connector.StatusChoices.BUSY
        self.connector.save()

        response = self.client.post(
            '/api/v1/bookings/',
            {'connector_id': self.connector.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_booking_duplicate_station(self):
        # Create first booking
        self.client.post(
            '/api/v1/bookings/',
            {'connector_id': self.connector.pk},
            format='json',
        )

        # Create second connector on same station
        connector2 = Connector.objects.create(
            station=self.station,
            connector_type='ccs',
            power_kw=50,
            price_per_kwh='10.00',
            status='free',
            connector_number=2,
        )

        response = self.client.post(
            '/api/v1/bookings/',
            {'connector_id': connector2.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_booking(self):
        # Create a booking first
        create_resp = self.client.post(
            '/api/v1/bookings/',
            {'connector_id': self.connector.pk},
            format='json',
        )
        booking_id = create_resp.data['id']

        response = self.client.delete(f'/api/v1/bookings/{booking_id}/cancel/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        booking = Booking.objects.get(pk=booking_id)
        self.assertEqual(booking.status, Booking.StatusChoices.CANCELLED)

        self.connector.refresh_from_db()
        self.assertEqual(self.connector.status, Connector.StatusChoices.FREE)

    def test_cancel_nonexistent_booking(self):
        response = self.client.delete('/api/v1/bookings/99999/cancel/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_bookings(self):
        # Create a booking
        self.client.post(
            '/api/v1/bookings/',
            {'connector_id': self.connector.pk},
            format='json',
        )

        response = self.client.get('/api/v1/bookings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_booking_is_expired_property(self):
        booking = Booking.objects.create(
            user=self.user,
            connector=self.connector,
            booking_fee=Decimal('50.00'),
            expires_at=timezone.now() + timedelta(minutes=20),
        )
        # Force expires_at to the past
        Booking.objects.filter(pk=booking.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        booking.refresh_from_db()
        self.assertTrue(booking.is_expired)

    def test_booking_sends_notification(self):
        self.client.post(
            '/api/v1/bookings/',
            {'connector_id': self.connector.pk},
            format='json',
        )

        notification = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.TypeChoices.BOOKING_CREATED,
        )
        self.assertTrue(notification.exists())

    def test_expire_bookings_task(self):
        # Create a booking
        booking = Booking(
            user=self.user,
            connector=self.connector,
            booking_fee=Decimal('50.00'),
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        booking.expires_at = timezone.now() - timedelta(minutes=1)
        booking.save()
        # Override expires_at after save since save() might set it
        Booking.objects.filter(pk=booking.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        expire_bookings()

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.StatusChoices.EXPIRED)

        self.connector.refresh_from_db()
        self.assertEqual(self.connector.status, Connector.StatusChoices.FREE)
