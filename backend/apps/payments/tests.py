from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.payments.models import Wallet, WalletTransaction
from apps.stations.models import Connector, Station
from apps.users.models import User


class PaymentTestCase(APITestCase):
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

    def test_get_wallet(self):
        response = self.client.get('/api/v1/payments/wallet/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data['balance']), Decimal('0.00'))

    def test_topup_initiate(self):
        response = self.client.post(
            '/api/v1/payments/wallet/topup/',
            {'amount': '1000.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('deeplink_url', response.data)
        self.assertEqual(Decimal(response.data['amount']), Decimal('1000.00'))

    def test_topup_callback(self):
        response = self.client.post(
            '/api/v1/payments/wallet/topup/callback/',
            {
                'user_id': self.user.pk,
                'amount': '1000.00',
                'success': True,
                'transaction_ref': 'ref123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        wallet = Wallet.objects.get(user=self.user)
        self.assertEqual(wallet.balance, Decimal('1000.00'))

    def test_topup_callback_failed(self):
        response = self.client.post(
            '/api/v1/payments/wallet/topup/callback/',
            {
                'user_id': self.user.pk,
                'amount': '1000.00',
                'success': False,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_topup_callback_missing_params(self):
        response = self.client.post(
            '/api/v1/payments/wallet/topup/callback/',
            {
                'amount': '1000.00',
                'success': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_wallet_transactions(self):
        # Perform a topup callback to create a transaction
        self.client.post(
            '/api/v1/payments/wallet/topup/callback/',
            {
                'user_id': self.user.pk,
                'amount': '500.00',
                'success': True,
                'transaction_ref': 'ref456',
            },
            format='json',
        )

        response = self.client.get('/api/v1/payments/wallet/transactions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(
            response.data['results'][0]['transaction_type'],
            WalletTransaction.TypeChoices.TOPUP,
        )

    def test_qr_payment_initiate(self):
        response = self.client.post(
            '/api/v1/payments/qr-payment/',
            {
                'connector_id': self.connector.pk,
                'amount': '500.00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('qr_url', response.data)
        self.assertEqual(Decimal(response.data['amount']), Decimal('500.00'))
        self.assertEqual(response.data['connector_id'], self.connector.pk)

    def test_wallet_auto_created(self):
        """Wallet is auto-created for new users via signal with zero balance."""
        user2 = User.objects.create_user(phone='+79997654321')
        # Signal auto-creates wallet
        self.assertTrue(Wallet.objects.filter(user=user2).exists())
        wallet = Wallet.objects.get(user=user2)
        self.assertEqual(wallet.balance, Decimal('0.00'))

        # And GET endpoint returns it
        refresh2 = RefreshToken.for_user(user2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh2.access_token}')
        response = self.client.get('/api/v1/payments/wallet/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data['balance']), Decimal('0.00'))
