from django.urls import path
from .views import (
    WalletView,
    TopUpInitiateView,
    TopUpCallbackView,
    WalletTransactionListView,
    QRPaymentInitiateView,
)

urlpatterns = [
    path('wallet/', WalletView.as_view(), name='wallet'),
    path('wallet/topup/', TopUpInitiateView.as_view(), name='wallet-topup'),
    path('wallet/topup/callback/', TopUpCallbackView.as_view(), name='wallet-topup-callback'),
    path('wallet/transactions/', WalletTransactionListView.as_view(), name='wallet-transactions'),
    path('qr-payment/', QRPaymentInitiateView.as_view(), name='qr-payment'),
]
