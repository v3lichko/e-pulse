import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('evcharging')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

from celery.schedules import crontab

app.conf.beat_schedule = {
    'expire-bookings-every-minute': {
        'task': 'apps.bookings.tasks.expire_bookings',
        'schedule': 60.0,
    },
    'complete-expired-sessions-hourly': {
        'task': 'apps.charging.tasks.complete_expired_sessions',
        'schedule': 3600.0,
    },
}
