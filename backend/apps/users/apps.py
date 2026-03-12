from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'apps.users'
    verbose_name = 'Пользователи'

    def ready(self):
        import apps.payments.signals  # noqa
