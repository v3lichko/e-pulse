from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    name = 'apps.payments'
    verbose_name = 'Платежи'

    def ready(self):
        import apps.payments.signals  # noqa
