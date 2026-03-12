from django.contrib import admin
from .models import Wallet, WalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'updated_at']
    search_fields = ['user__phone']
    ordering = ['-updated_at']
    readonly_fields = ['updated_at']


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'wallet', 'amount', 'transaction_type', 'description', 'created_at'
    ]
    list_filter = ['transaction_type']
    search_fields = ['wallet__user__phone', 'description']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
