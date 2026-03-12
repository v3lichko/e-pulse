from django.db import models


class Station(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название')
    address = models.CharField(max_length=500, verbose_name='Адрес')
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, verbose_name='Широта'
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, verbose_name='Долгота'
    )
    image = models.ImageField(
        upload_to='stations/', blank=True, null=True, verbose_name='Изображение'
    )
    description = models.TextField(blank=True, verbose_name='Описание')
    working_hours = models.CharField(
        max_length=100, blank=True, default='24/7', verbose_name='Часы работы'
    )
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлена')

    class Meta:
        verbose_name = 'Зарядная станция'
        verbose_name_plural = 'Зарядные станции'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def status(self):
        connectors = self.connectors.all()
        if not connectors.exists():
            return 'unknown'
        statuses = set(connectors.values_list('status', flat=True))
        if Connector.StatusChoices.FREE in statuses:
            return 'free'
        if Connector.StatusChoices.RESERVED in statuses:
            return 'reserved'
        if Connector.StatusChoices.BUSY in statuses:
            return 'busy'
        if all(s == Connector.StatusChoices.BROKEN for s in statuses):
            return 'broken'
        return 'unknown'


class Connector(models.Model):
    class TypeChoices(models.TextChoices):
        TYPE2 = 'type2', 'Type 2'
        CCS = 'ccs', 'CCS'
        CHADEMO = 'chademo', 'CHAdeMO'
        TYPE1 = 'type1', 'Type 1'

    class StatusChoices(models.TextChoices):
        FREE = 'free', 'Свободен'
        BUSY = 'busy', 'Занят'
        BROKEN = 'broken', 'Неисправен'
        RESERVED = 'reserved', 'Забронирован'

    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name='connectors',
        verbose_name='Станция'
    )
    connector_type = models.CharField(
        max_length=20,
        choices=TypeChoices.choices,
        default=TypeChoices.TYPE2,
        verbose_name='Тип разъёма'
    )
    power_kw = models.DecimalField(
        max_digits=6, decimal_places=2, verbose_name='Мощность (кВт)'
    )
    price_per_kwh = models.DecimalField(
        max_digits=6, decimal_places=2, verbose_name='Цена за кВт·ч (₽)'
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.FREE,
        verbose_name='Статус'
    )
    connector_number = models.IntegerField(verbose_name='Номер разъёма')
    image = models.ImageField(
        upload_to='connectors/', blank=True, null=True, verbose_name='Изображение'
    )
    ocpp_connector_id = models.IntegerField(default=1, verbose_name='OCPP ID разъёма')

    class Meta:
        verbose_name = 'Разъём'
        verbose_name_plural = 'Разъёмы'
        ordering = ['connector_number']

    def __str__(self):
        return f'{self.station.name} - {self.connector_type} #{self.connector_number}'
