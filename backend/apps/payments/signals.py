from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='users.User')
def create_wallet_for_user(sender, instance, created, **kwargs):
    if created:
        from .models import Wallet
        Wallet.objects.get_or_create(user=instance)
