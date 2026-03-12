import logging
import random
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='apps.charging.tasks.update_charging_meters')
def update_charging_meters(session_id):
    """
    Periodic task to simulate meter value updates during charging.
    In production, this would receive real data from OCPP MeterValues messages.
    """
    try:
        from .models import ChargingSession
        session = ChargingSession.objects.select_related('connector').get(
            pk=session_id,
            status=ChargingSession.StatusChoices.ACTIVE,
        )

        # Simulate power reading between 80-100% of connector power
        power_fraction = random.uniform(0.8, 1.0)
        current_power = float(session.connector.power_kw) * power_fraction

        # Calculate energy added since last update (assuming called every minute)
        energy_added = Decimal(str(current_power / 60))  # kWh in 1 minute

        session.energy_kwh = session.energy_kwh + energy_added
        session.current_power_kw = Decimal(str(round(current_power, 2)))
        session.cost = session.energy_kwh * session.connector.price_per_kwh
        session.save(update_fields=['energy_kwh', 'current_power_kw', 'cost'])

        logger.debug(
            f'Session {session_id}: energy={session.energy_kwh} kWh, '
            f'power={session.current_power_kw} kW, cost={session.cost}₽'
        )

        # Send energy update notification
        try:
            from apps.notifications.services import NotificationService
            NotificationService.send_energy_update(session.user, session)
        except Exception as e:
            logger.warning(f'Failed to send energy update notification: {e}')

    except Exception as e:
        logger.error(f'Error updating charging meters for session {session_id}: {e}')


@shared_task(name='apps.charging.tasks.complete_expired_sessions')
def complete_expired_sessions():
    """
    Find sessions that have been active for more than 8 hours without updates
    and complete them automatically.
    """
    from .models import ChargingSession, Receipt
    from apps.stations.models import Connector

    cutoff_time = timezone.now() - timezone.timedelta(hours=8)

    expired_sessions = ChargingSession.objects.filter(
        status=ChargingSession.StatusChoices.ACTIVE,
        start_time__lt=cutoff_time,
    ).select_related('connector__station', 'user')

    completed_count = 0
    for session in expired_sessions:
        try:
            final_cost = session.energy_kwh * session.connector.price_per_kwh

            session.end_time = timezone.now()
            session.cost = final_cost
            session.status = ChargingSession.StatusChoices.COMPLETED
            session.save()

            # Free connector
            session.connector.status = Connector.StatusChoices.FREE
            session.connector.save()

            # Create receipt if doesn't exist
            if not hasattr(session, 'receipt'):
                Receipt.objects.create(
                    session=session,
                    station_name=session.connector.station.name,
                    station_address=session.connector.station.address,
                    connector_type=session.connector.connector_type,
                    energy_kwh=session.energy_kwh,
                    cost=session.cost,
                    payment_method=session.payment_method,
                    start_time=session.start_time,
                    end_time=session.end_time,
                    receipt_number=Receipt.generate_receipt_number(),
                )

            completed_count += 1
            logger.info(f'Auto-completed expired session {session.pk}')

        except Exception as e:
            logger.error(f'Error completing expired session {session.pk}: {e}')

    if completed_count:
        logger.info(f'Auto-completed {completed_count} expired charging sessions')

    return completed_count
