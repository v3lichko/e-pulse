from django.db import models


class Wallet(models.Model):
    user = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        related_name='wallet',
        verbose_name='Пользователь'
    )
    balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name='Баланс (₽)'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлён')

    class Meta:
        verbose_name = 'Кошелёк'
        verbose_name_plural = 'Кошельки'

    def __str__(self):
        return f'Кошелёк {self.user} - {self.balance}₽'


class WalletTransaction(models.Model):
    class TypeChoices(models.TextChoices):
        TOPUP = 'topup', 'Пополнение'
        CHARGE = 'charge', 'Оплата зарядки'
        BOOKING = 'booking', 'Оплата брони'
        REFUND = 'refund', 'Возврат'

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name='Кошелёк'
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Сумма (₽)'
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TypeChoices.choices,
        verbose_name='Тип транзакции'
    )
    description = models.CharField(
        max_length=500, verbose_name='Описание'
    )
    session = models.ForeignKey(
        'charging.ChargingSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_transactions',
        verbose_name='Сессия зарядки'
    )
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_transactions',
        verbose_name='Бронь'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')

    class Meta:
        verbose_name = 'Транзакция'
        verbose_name_plural = 'Транзакции'
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f'{self.get_transaction_type_display()} {sign}{self.amount}₽'
