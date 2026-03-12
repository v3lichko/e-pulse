from decimal import Decimal
from unittest.mock import MagicMock

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.notifications.models import Notification, PushToken
from apps.notifications.services import NotificationService
from apps.stations.models import Connector, Station
from apps.users.models import User


class NotificationTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='+79991234567')
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        self.station = Station.objects.create(
            name='Test Station', address='addr', latitude=55.75, longitude=37.62
        )
        self.connector = Connector.objects.create(
            station=self.station,
            connector_type='type2',
            power_kw=22,
            price_per_kwh='8.50',
            status='free',
            connector_number=1,
        )

    def test_register_push_token(self):
        response = self.client.post(
            '/api/v1/notifications/push-token/',
            {'token': 'fcm-token-abc123', 'platform': 'android'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            PushToken.objects.filter(
                user=self.user, token='fcm-token-abc123', platform='android'
            ).exists()
        )

    def test_register_push_token_update(self):
        # Register same token twice
        self.client.post(
            '/api/v1/notifications/push-token/',
            {'token': 'fcm-token-abc123', 'platform': 'android'},
            format='json',
        )
        self.client.post(
            '/api/v1/notifications/push-token/',
            {'token': 'fcm-token-abc123', 'platform': 'android'},
            format='json',
        )
        self.assertEqual(
            PushToken.objects.filter(token='fcm-token-abc123').count(), 1
        )

    def test_list_notifications(self):
        Notification.objects.create(
            user=self.user,
            title='Test 1',
            body='Body 1',
            notification_type='charging_start',
        )
        Notification.objects.create(
            user=self.user,
            title='Test 2',
            body='Body 2',
            notification_type='charging_end',
        )

        response = self.client.get('/api/v1/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_mark_read(self):
        notification = Notification.objects.create(
            user=self.user,
            title='Test',
            body='Body',
            notification_type='charging_start',
        )
        self.assertFalse(notification.is_read)

        response = self.client.post(
            f'/api/v1/notifications/{notification.pk}/read/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_mark_all_read(self):
        Notification.objects.create(
            user=self.user,
            title='Test 1',
            body='Body 1',
            notification_type='charging_start',
        )
        Notification.objects.create(
            user=self.user,
            title='Test 2',
            body='Body 2',
            notification_type='charging_end',
        )

        response = self.client.post('/api/v1/notifications/read-all/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        unread = Notification.objects.filter(user=self.user, is_read=False).count()
        self.assertEqual(unread, 0)

    def test_notification_service_send(self):
        notification = NotificationService.send_push(
            user=self.user,
            title='Push Title',
            body='Push Body',
            data={'key': 'value'},
            notification_type=Notification.TypeChoices.STATION_AVAILABLE,
        )
        self.assertIsNotNone(notification)
        self.assertTrue(
            Notification.objects.filter(
                user=self.user,
                title='Push Title',
                body='Push Body',
                notification_type=Notification.TypeChoices.STATION_AVAILABLE,
            ).exists()
        )

    def test_notification_service_charging_started(self):
        session = MagicMock()
        session.pk = 1
        session.connector = self.connector

        notification = NotificationService.send_charging_started(self.user, session)
        self.assertEqual(notification.notification_type, Notification.TypeChoices.CHARGING_START)
        self.assertIn('Test Station', notification.body)

    def test_notification_service_booking_created(self):
        from apps.bookings.models import Booking

        booking = Booking.objects.create(
            user=self.user,
            connector=self.connector,
            booking_fee=Decimal('50.00'),
        )

        notification = NotificationService.send_booking_created(self.user, booking)
        self.assertEqual(
            notification.notification_type, Notification.TypeChoices.BOOKING_CREATED
        )
        self.assertIn('50', notification.body)
        self.assertIn('20', notification.body)

    def test_unauthenticated(self):
        self.client.credentials()  # Clear auth
        response = self.client.get('/api/v1/notifications/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
