import django_filters
from .models import Station, Connector


class StationFilter(django_filters.FilterSet):
    connector_type = django_filters.CharFilter(
        field_name='connectors__connector_type',
        lookup_expr='exact',
        label='Тип разъёма'
    )
    min_power = django_filters.NumberFilter(
        field_name='connectors__power_kw',
        lookup_expr='gte',
        label='Минимальная мощность (кВт)'
    )
    max_power = django_filters.NumberFilter(
        field_name='connectors__power_kw',
        lookup_expr='lte',
        label='Максимальная мощность (кВт)'
    )
    status = django_filters.CharFilter(
        field_name='connectors__status',
        lookup_expr='exact',
        label='Статус разъёма'
    )

    class Meta:
        model = Station
        fields = ['connector_type', 'min_power', 'max_power', 'status']
