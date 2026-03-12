from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.stations.models import Station
from apps.users.models import FavoriteStation, OTPCode, User


class OTPTests(APITestCase):
    """Tests for OTP send and verify endpoints."""

    SEND_OTP_URL = '/api/v1/auth/send-otp/'
    VERIFY_OTP_URL = '/api/v1/auth/verify-otp/'

    @override_settings(DEBUG=True)
    def test_send_otp_success(self):
        """POST with valid phone returns 200 and code in DEBUG mode."""
        response = self.client.post(self.SEND_OTP_URL, {'phone': '+79991234567'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('code', response.data)
        self.assertEqual(len(response.data['code']), 6)

    def test_send_otp_invalid_phone(self):
        """POST with invalid phone returns 400."""
        response = self.client.post(self.SEND_OTP_URL, {'phone': 'not-a-phone'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(DEBUG=True)
    def test_verify_otp_success(self):
        """Send OTP then verify returns tokens and user data."""
        send_resp = self.client.post(self.SEND_OTP_URL, {'phone': '+79991234567'})
        code = send_resp.data['code']

        response = self.client.post(self.VERIFY_OTP_URL, {
            'phone': '+79991234567',
            'code': code,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])
        self.assertIn('user', response.data)

    @override_settings(DEBUG=True)
    def test_verify_otp_creates_new_user(self):
        """Verify OTP creates a new user if none exists."""
        self.assertFalse(User.objects.filter(phone='+79991234567').exists())

        send_resp = self.client.post(self.SEND_OTP_URL, {'phone': '+79991234567'})
        code = send_resp.data['code']

        response = self.client.post(self.VERIFY_OTP_URL, {
            'phone': '+79991234567',
            'code': code,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_new_user'])
        self.assertTrue(User.objects.filter(phone='+79991234567').exists())

    @override_settings(DEBUG=True)
    def test_verify_otp_existing_user(self):
        """Verify OTP for existing user returns is_new_user=False."""
        User.objects.create_user(phone='+79991234567')

        send_resp = self.client.post(self.SEND_OTP_URL, {'phone': '+79991234567'})
        code = send_resp.data['code']

        response = self.client.post(self.VERIFY_OTP_URL, {
            'phone': '+79991234567',
            'code': code,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_new_user'])

    def test_verify_otp_wrong_code(self):
        """Verify with wrong code returns 400."""
        OTPCode.generate('+79991234567')

        response = self.client.post(self.VERIFY_OTP_URL, {
            'phone': '+79991234567',
            'code': '000000',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_otp_expired(self):
        """Verify with expired OTP returns 400."""
        otp = OTPCode.generate('+79991234567')
        # Force the OTP to be expired
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save()

        response = self.client.post(self.VERIFY_OTP_URL, {
            'phone': '+79991234567',
            'code': otp.code,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ProfileTests(APITestCase):
    """Tests for the user profile endpoint."""

    PROFILE_URL = '/api/v1/auth/profile/'

    def setUp(self):
        self.user = User.objects.create_user(phone='+79991234567')
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_get_profile(self):
        """Authenticated GET returns user profile data."""
        response = self.client.get(self.PROFILE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.user.id)
        self.assertEqual(response.data['phone'], str(self.user.phone))

    def test_update_profile_name(self):
        """PATCH with name updates the user name."""
        response = self.client.patch(self.PROFILE_URL, {'name': 'Test User'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, 'Test User')

    def test_delete_profile(self):
        """DELETE deactivates the account instead of deleting it."""
        response = self.client.delete(self.PROFILE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_profile_unauthenticated(self):
        """GET without token returns 401."""
        self.client.credentials()  # Clear credentials
        response = self.client.get(self.PROFILE_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class FavoritesTests(APITestCase):
    """Tests for favorite station endpoints."""

    FAVORITES_URL = '/api/v1/auth/favorites/'

    def setUp(self):
        self.user = User.objects.create_user(phone='+79991234567')
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        self.station = Station.objects.create(
            name='Test',
            address='Test addr',
            latitude=55.75,
            longitude=37.62,
        )

    def _toggle_url(self, station_id):
        return f'{self.FAVORITES_URL}{station_id}/'

    def test_add_favorite(self):
        """POST adds station to favorites."""
        response = self.client.post(self._toggle_url(self.station.id))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            FavoriteStation.objects.filter(user=self.user, station=self.station).exists()
        )

    def test_add_favorite_duplicate(self):
        """POST for already-favorited station returns 200."""
        FavoriteStation.objects.create(user=self.user, station=self.station)

        response = self.client.post(self._toggle_url(self.station.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_remove_favorite(self):
        """DELETE removes station from favorites."""
        FavoriteStation.objects.create(user=self.user, station=self.station)

        response = self.client.delete(self._toggle_url(self.station.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            FavoriteStation.objects.filter(user=self.user, station=self.station).exists()
        )

    def test_list_favorites(self):
        """GET returns list of user favorites."""
        FavoriteStation.objects.create(user=self.user, station=self.station)

        response = self.client.get(self.FAVORITES_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)

    def test_favorite_nonexistent_station(self):
        """POST for nonexistent station returns 404."""
        response = self.client.post(self._toggle_url(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
