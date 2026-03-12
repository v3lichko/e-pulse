import random
import string
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField


class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError('Номер телефона обязателен')
        user = self.model(phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Суперпользователь должен иметь is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Суперпользователь должен иметь is_superuser=True.')

        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    phone = PhoneNumberField(unique=True, verbose_name='Номер телефона')
    name = models.CharField(max_length=100, blank=True, verbose_name='Имя')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    is_staff = models.BooleanField(default=False, verbose_name='Персонал')
    date_joined = models.DateTimeField(default=timezone.now, verbose_name='Дата регистрации')

    objects = UserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return str(self.phone)

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name


class OTPCode(models.Model):
    phone = models.CharField(max_length=20, verbose_name='Номер телефона')
    code = models.CharField(max_length=6, verbose_name='Код')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    expires_at = models.DateTimeField(verbose_name='Истекает')
    is_used = models.BooleanField(default=False, verbose_name='Использован')

    class Meta:
        verbose_name = 'OTP-код'
        verbose_name_plural = 'OTP-коды'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.phone} - {self.code}'

    @classmethod
    def generate(cls, phone):
        code = ''.join(random.choices(string.digits, k=6))
        expires_at = timezone.now() + timedelta(minutes=5)
        # Invalidate existing codes for this phone
        cls.objects.filter(phone=str(phone), is_used=False).update(is_used=True)
        otp = cls.objects.create(
            phone=str(phone),
            code=code,
            expires_at=expires_at,
        )
        return otp

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at


class FavoriteStation(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name='Пользователь'
    )
    station = models.ForeignKey(
        'stations.Station',
        on_delete=models.CASCADE,
        related_name='favorited_by',
        verbose_name='Станция'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Добавлено')

    class Meta:
        verbose_name = 'Избранная станция'
        verbose_name_plural = 'Избранные станции'
        unique_together = ('user', 'station')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} - {self.station}'
