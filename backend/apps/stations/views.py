import logging

from django_filters.rest_framework import DjangoFilterBackend
from haversine import haversine, Unit
from rest_framework import generics
from rest_framework.filters import SearchFilter
from rest_framework.permissions import AllowAny

from .filters import StationFilter
from .models import Station
from .serializers import StationListSerializer, StationDetailSerializer

logger = logging.getLogger(__name__)


class StationListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = StationListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = StationFilter
    search_fields = ['name', 'address']

    def get_queryset(self):
        queryset = Station.objects.filter(
            is_active=True
        ).prefetch_related('connectors').distinct()

        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')
        radius = self.request.query_params.get('radius', 50)

        if lat and lng:
            try:
                lat = float(lat)
                lng = float(lng)
                radius = float(radius)
                user_location = (lat, lng)

                filtered = []
                for station in queryset:
                    station_location = (float(station.latitude), float(station.longitude))
                    distance = haversine(user_location, station_location, unit=Unit.KILOMETERS)
                    if distance <= radius:
                        filtered.append(station.pk)
                queryset = queryset.filter(pk__in=filtered)
            except (ValueError, TypeError) as e:
                logger.warning(f'Invalid lat/lng parameters: {e}')

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['lat'] = self.request.query_params.get('lat')
        context['lng'] = self.request.query_params.get('lng')
        return context


class StationDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = StationDetailSerializer
    queryset = Station.objects.filter(is_active=True).prefetch_related('connectors')


class NearbyStationsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = StationListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = StationFilter
    search_fields = ['name', 'address']

    def get_queryset(self):
        queryset = Station.objects.filter(
            is_active=True
        ).prefetch_related('connectors').distinct()

        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')
        radius = self.request.query_params.get('radius', 50)

        if not lat or not lng:
            return queryset.none()

        try:
            lat = float(lat)
            lng = float(lng)
            radius = float(radius)
            user_location = (lat, lng)

            stations_with_distance = []
            for station in queryset:
                station_location = (float(station.latitude), float(station.longitude))
                distance = haversine(user_location, station_location, unit=Unit.KILOMETERS)
                if distance <= radius:
                    stations_with_distance.append((station.pk, distance))

            stations_with_distance.sort(key=lambda x: x[1])
            sorted_ids = [pk for pk, _ in stations_with_distance]

            # Preserve ordering
            from django.db.models import Case, When, IntegerField
            cases = [When(pk=pk, then=pos) for pos, pk in enumerate(sorted_ids)]
            if cases:
                queryset = queryset.filter(pk__in=sorted_ids).annotate(
                    order=Case(*cases, output_field=IntegerField())
                ).order_by('order')
            else:
                queryset = queryset.none()

        except (ValueError, TypeError) as e:
            logger.warning(f'Invalid parameters in NearbyStationsView: {e}')
            return queryset.none()

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['lat'] = self.request.query_params.get('lat')
        context['lng'] = self.request.query_params.get('lng')
        return context
