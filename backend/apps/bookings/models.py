from datetime import timedelta

from django.db import models
from django.utils import timezone


class Booking(models.Model):
    class StatusChoices(models.TextChoices):
        ACTIVE = 'active', 'Активна'
        EXPIRED = 'expired', 'Истекла'
        USED = 'used', 'Использована'
        CANCELLED = 'cancelled', 'Отменена'

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='bookings',
        verbose_name='Пользователь'
    )
    connector = models.ForeignKey(
        'stations.Connector',
        on_delete=models.PROTECT,
        related_name='bookings',
        verbose_name='Разъём'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    expires_at = models.DateTimeField(verbose_name='Истекает')
    booking_fee = models.DecimalField(
        max_digits=6, decimal_places=2, verbose_name='Стоимость брони (₽)'
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE,
        verbose_name='Статус'
    )

    class Meta:
        verbose_name = 'Бронь'
        verbose_name_plural = 'Брони'
        ordering = ['-created_at']

    def __str__(self):
        return f'Бронь #{self.pk} - {self.user} ({self.status})'

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new and not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=20)
        super().save(*args, **kwargs)
        if is_new:
            from apps.stations.models import Connector
            self.connector.status = Connector.StatusChoices.RESERVED
            self.connector.save()

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def cancel(self):
        from apps.stations.models import Connector
        self.status = self.StatusChoices.CANCELLED
        self.save()
        self.connector.status = Connector.StatusChoices.FREE
        self.connector.save()
