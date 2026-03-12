from django.urls import path
from .views import (
    RegisterPushTokenView,
    NotificationListView,
    MarkReadView,
    MarkAllReadView,
)

urlpatterns = [
    path('push-token/', RegisterPushTokenView.as_view(), name='push-token-register'),
    path('', NotificationListView.as_view(), name='notification-list'),
    path('<int:pk>/read/', MarkReadView.as_view(), name='notification-read'),
    path('read-all/', MarkAllReadView.as_view(), name='notification-read-all'),
]
