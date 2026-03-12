import logging

from django.conf import settings

from .models import PushToken, Notification

logger = logging.getLogger(__name__)


def _get_firebase_app():
    """Initialize and return Firebase app, or None if not configured."""
    try:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            cred_path = settings.FIREBASE_CREDENTIALS_PATH
            if not cred_path:
                logger.warning('FIREBASE_CREDENTIALS_PATH not configured')
                return None
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

        return firebase_admin.get_app()
    except Exception as e:
        logger.warning(f'Firebase initialization failed: {e}')
        return None


class NotificationService:

    @classmethod
    def send_push(cls, user, title, body, data=None, notification_type=None):
        """
        Send push notification to user and save to DB.
        """
        if data is None:
            data = {}
        if notification_type is None:
            notification_type = Notification.TypeChoices.STATION_AVAILABLE

        # Save notification to DB
        notification = Notification.objects.create(
            user=user,
            title=title,
            body=body,
            notification_type=notification_type,
            data=data,
        )

        # Get user's push tokens
        tokens = list(
            PushToken.objects.filter(user=user).values_list('token', flat=True)
        )

        if not tokens:
            logger.debug(f'No push tokens for user {user.pk}')
            return notification

        # Send via Firebase
        firebase_app = _get_firebase_app()
        if firebase_app:
            try:
                from firebase_admin import messaging

                # Prepare data as string values (Firebase requirement)
                str_data = {k: str(v) for k, v in data.items()}

                message = messaging.MulticastMessage(
                    notification=messaging.Notification(title=title, body=body),
                    data=str_data,
                    tokens=tokens,
                )
                response = messaging.send_each_for_multicast(message)
                logger.info(
                    f'Firebase push sent to {user.pk}: '
                    f'{response.success_count} success, {response.failure_count} failures'
                )

                # Clean up invalid tokens
                if response.failure_count > 0:
                    for idx, resp in enumerate(response.responses):
                        if not resp.success:
                            invalid_token = tokens[idx]
                            PushToken.objects.filter(token=invalid_token).delete()
                            logger.info(f'Removed invalid token: {invalid_token[:20]}...')

            except Exception as e:
                logger.error(f'Firebase push failed for user {user.pk}: {e}')
        else:
            logger.info(
                f'[DEV] Push notification for {user.pk}: {title} - {body}'
            )

        return notification

    @classmethod
    def send_charging_started(cls, user, session):
        station_name = session.connector.station.name
        return cls.send_push(
            user=user,
            title='Зарядка началась',
            body=f'Зарядка на станции "{station_name}" успешно начата.',
            data={
                'session_id': str(session.pk),
                'connector_id': str(session.connector.pk),
            },
            notification_type=Notification.TypeChoices.CHARGING_START,
        )

    @classmethod
    def send_charging_completed(cls, user, session, receipt):
        return cls.send_push(
            user=user,
            title='Зарядка завершена',
            body=(
                f'Зарядка завершена. '
                f'Получено {session.energy_kwh} кВт·ч, '
                f'стоимость: {session.cost}₽.'
            ),
            data={
                'session_id': str(session.pk),
                'receipt_id': str(receipt.pk),
                'receipt_number': receipt.receipt_number,
                'energy_kwh': str(session.energy_kwh),
                'cost': str(session.cost),
            },
            notification_type=Notification.TypeChoices.CHARGING_END,
        )

    @classmethod
    def send_booking_created(cls, user, booking):
        return cls.send_push(
            user=user,
            title='Бронь создана',
            body=(
                f'Бронь создана. Стоимость: {booking.booking_fee}₽. '
                f'Если вы приедете и начнёте зарядку в течение 20 минут, '
                f'эта сумма покроет часть стоимости зарядки.'
            ),
            data={
                'booking_id': str(booking.pk),
                'connector_id': str(booking.connector.pk),
                'expires_at': booking.expires_at.isoformat(),
            },
            notification_type=Notification.TypeChoices.BOOKING_CREATED,
        )

    @classmethod
    def send_booking_expired(cls, user, booking):
        station_name = booking.connector.station.name
        return cls.send_push(
            user=user,
            title='Бронь истекла',
            body=f'Ваша бронь на станции "{station_name}" истекла.',
            data={
                'booking_id': str(booking.pk),
            },
            notification_type=Notification.TypeChoices.BOOKING_EXPIRED,
        )

    @classmethod
    def send_energy_update(cls, user, session):
        return cls.send_push(
            user=user,
            title='Обновление зарядки',
            body=(
                f'Получено {session.energy_kwh} кВт·ч, '
                f'стоимость: {session.cost}₽.'
            ),
            data={
                'session_id': str(session.pk),
                'energy_kwh': str(session.energy_kwh),
                'cost': str(session.cost),
                'current_power_kw': str(session.current_power_kw),
            },
            notification_type=Notification.TypeChoices.ENERGY_UPDATE,
        )
