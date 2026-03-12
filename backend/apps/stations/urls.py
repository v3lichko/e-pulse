from django.urls import path
from .views import StationListView, StationDetailView, NearbyStationsView

urlpatterns = [
    path('', StationListView.as_view(), name='station-list'),
    path('nearby/', NearbyStationsView.as_view(), name='station-nearby'),
    path('<int:pk>/', StationDetailView.as_view(), name='station-detail'),
]
