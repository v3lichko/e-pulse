from django.urls import path
from .views import (
    StartChargingView,
    StopChargingView,
    ActiveSessionView,
    ChargingHistoryView,
    ReceiptView,
)

urlpatterns = [
    path('start/', StartChargingView.as_view(), name='charging-start'),
    path('stop/', StopChargingView.as_view(), name='charging-stop'),
    path('active/', ActiveSessionView.as_view(), name='charging-active'),
    path('history/', ChargingHistoryView.as_view(), name='charging-history'),
    path('<int:session_id>/receipt/', ReceiptView.as_view(), name='charging-receipt'),
]
