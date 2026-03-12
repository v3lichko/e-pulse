import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='apps.bookings.tasks.expire_bookings')
def expire_bookings():
    """
    Find expired bookings and update their status.
    Frees up connectors that were reserved for expired bookings.
    """
    from .models import Booking
    from apps.stations.models import Connector

    now = timezone.now()
    expired_bookings = Booking.objects.filter(
        status=Booking.StatusChoices.ACTIVE,
        expires_at__lt=now,
    ).select_related('connector', 'user')

    expired_count = 0
    for booking in expired_bookings:
        try:
            # Update booking status
            booking.status = Booking.StatusChoices.EXPIRED
            booking.save()

            # Free connector
            connector = booking.connector
            connector.status = Connector.StatusChoices.FREE
            connector.save()

            # Send expiry notification
            try:
                from apps.notifications.services import NotificationService
                NotificationService.send_booking_expired(booking.user, booking)
            except Exception as e:
                logger.warning(f'Failed to send expiry notification for booking {booking.pk}: {e}')

            expired_count += 1
            logger.info(f'Expired booking {booking.pk} for user {booking.user}')

        except Exception as e:
            logger.error(f'Error expiring booking {booking.pk}: {e}')

    if expired_count:
        logger.info(f'Expired {expired_count} bookings')

    return expired_count
