import uuid
from django.db import models
from django.utils import timezone


class ChargingSession(models.Model):
    class PaymentMethodChoices(models.TextChoices):
        WALLET = 'wallet', 'Кошелёк'
        QR = 'qr', 'QR-код'

    class StatusChoices(models.TextChoices):
        ACTIVE = 'active', 'Активна'
        COMPLETED = 'completed', 'Завершена'
        CANCELLED = 'cancelled', 'Отменена'

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='charging_sessions',
        verbose_name='Пользователь'
    )
    connector = models.ForeignKey(
        'stations.Connector',
        on_delete=models.PROTECT,
        related_name='sessions',
        verbose_name='Разъём'
    )
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions',
        verbose_name='Бронь'
    )
    start_time = models.DateTimeField(auto_now_add=True, verbose_name='Начало')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='Конец')
    energy_kwh = models.DecimalField(
        max_digits=8, decimal_places=3, default=0, verbose_name='Энергия (кВт·ч)'
    )
    cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name='Стоимость (₽)'
    )
    current_power_kw = models.DecimalField(
        max_digits=6, decimal_places=2, default=0, verbose_name='Текущая мощность (кВт)'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethodChoices.choices,
        default=PaymentMethodChoices.WALLET,
        verbose_name='Способ оплаты'
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE,
        verbose_name='Статус'
    )
    transaction_id = models.CharField(
        max_length=100, null=True, blank=True, verbose_name='ID транзакции'
    )
    ocpp_transaction_id = models.IntegerField(
        null=True, blank=True, verbose_name='OCPP ID транзакции'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')

    class Meta:
        verbose_name = 'Зарядная сессия'
        verbose_name_plural = 'Зарядные сессии'
        ordering = ['-start_time']

    def __str__(self):
        return f'Сессия #{self.pk} - {self.user} ({self.status})'

    @property
    def duration_seconds(self):
        end = self.end_time or timezone.now()
        return int((end - self.start_time).total_seconds())


class Receipt(models.Model):
    session = models.OneToOneField(
        ChargingSession,
        on_delete=models.CASCADE,
        related_name='receipt',
        verbose_name='Сессия'
    )
    station_name = models.CharField(max_length=200, verbose_name='Название станции')
    station_address = models.CharField(max_length=500, verbose_name='Адрес станции')
    connector_type = models.CharField(max_length=50, verbose_name='Тип разъёма')
    energy_kwh = models.DecimalField(
        max_digits=8, decimal_places=3, verbose_name='Энергия (кВт·ч)'
    )
    cost = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Стоимость (₽)'
    )
    payment_method = models.CharField(max_length=50, verbose_name='Способ оплаты')
    start_time = models.DateTimeField(verbose_name='Начало зарядки')
    end_time = models.DateTimeField(verbose_name='Конец зарядки')
    receipt_number = models.CharField(
        max_length=50, unique=True, verbose_name='Номер чека'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')

    class Meta:
        verbose_name = 'Чек'
        verbose_name_plural = 'Чеки'
        ordering = ['-created_at']

    def __str__(self):
        return f'Чек {self.receipt_number}'

    @classmethod
    def generate_receipt_number(cls):
        return f'RCP-{uuid.uuid4().hex[:10].upper()}'
