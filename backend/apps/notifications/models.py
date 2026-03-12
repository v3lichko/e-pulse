from django.db import models


class PushToken(models.Model):
    class PlatformChoices(models.TextChoices):
        IOS = 'ios', 'iOS'
        ANDROID = 'android', 'Android'

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='push_tokens',
        verbose_name='Пользователь'
    )
    token = models.CharField(max_length=500, unique=True, verbose_name='Токен')
    platform = models.CharField(
        max_length=10,
        choices=PlatformChoices.choices,
        verbose_name='Платформа'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлён')

    class Meta:
        verbose_name = 'Push-токен'
        verbose_name_plural = 'Push-токены'
        unique_together = ('user', 'token')
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.user} - {self.platform} ({self.token[:20]}...)'


class Notification(models.Model):
    class TypeChoices(models.TextChoices):
        CHARGING_START = 'charging_start', 'Начало зарядки'
        CHARGING_END = 'charging_end', 'Конец зарядки'
        BOOKING_CREATED = 'booking_created', 'Бронь создана'
        BOOKING_EXPIRED = 'booking_expired', 'Бронь истекла'
        STATION_AVAILABLE = 'station_available', 'Станция доступна'
        ENERGY_UPDATE = 'energy_update', 'Обновление энергии'

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Пользователь'
    )
    title = models.CharField(max_length=200, verbose_name='Заголовок')
    body = models.TextField(verbose_name='Текст')
    notification_type = models.CharField(
        max_length=30,
        choices=TypeChoices.choices,
        verbose_name='Тип уведомления'
    )
    data = models.JSONField(default=dict, blank=True, verbose_name='Данные')
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} - {self.title} ({self.notification_type})'
