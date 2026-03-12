import asyncio
import logging
import random
from datetime import datetime

from ocpp.routing import on
from ocpp.v16 import ChargePoint as cp
from ocpp.v16 import call_result
from ocpp.v16.enums import (
    Action,
    RegistrationStatus,
    AuthorizationStatus,
    ChargePointStatus,
)

logger = logging.getLogger(__name__)

OCPP_STATUS_MAP = {
    'Available': 'free',
    'Preparing': 'free',
    'Charging': 'busy',
    'SuspendedEVSE': 'busy',
    'SuspendedEV': 'busy',
    'Finishing': 'busy',
    'Reserved': 'reserved',
    'Unavailable': 'broken',
    'Faulted': 'broken',
}


class ChargePoint(cp):

    @on(Action.BootNotification)
    async def on_boot_notification(
        self, charge_point_vendor, charge_point_model, **kwargs
    ):
        logger.info(
            f'Boot notification from CP {self.id}: '
            f'{charge_point_vendor} {charge_point_model}'
        )
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S') + 'Z',
            interval=300,
            status=RegistrationStatus.accepted,
        )

    @on(Action.Heartbeat)
    async def on_heartbeat(self):
        logger.debug(f'Heartbeat from CP {self.id}')
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S') + 'Z',
        )

    @on(Action.StatusNotification)
    async def on_status_notification(
        self, connector_id, error_code, status, **kwargs
    ):
        logger.info(
            f'CP {self.id} connector {connector_id}: status={status}, '
            f'error_code={error_code}'
        )

        if connector_id > 0:
            try:
                from asgiref.sync import sync_to_async
                await sync_to_async(self._update_connector_status)(
                    connector_id, status
                )
            except Exception as e:
                logger.error(f'Error updating connector status: {e}')

        return call_result.StatusNotificationPayload()

    def _update_connector_status(self, connector_id, ocpp_status):
        from apps.stations.models import Connector, Station
        our_status = OCPP_STATUS_MAP.get(ocpp_status, 'free')

        try:
            # Try to find connector by ocpp_connector_id and charge_point_id
            # Charge point ID should map to station somehow
            # For now, update by connector's ocpp_connector_id
            connectors = Connector.objects.filter(
                ocpp_connector_id=connector_id,
            )
            for connector in connectors:
                connector.status = our_status
                connector.save()
                logger.info(
                    f'Updated connector {connector.pk} status to {our_status}'
                )
        except Exception as e:
            logger.error(f'DB error updating connector status: {e}')

    @on(Action.Authorize)
    async def on_authorize(self, id_tag, **kwargs):
        logger.info(f'Authorization request for id_tag: {id_tag}')
        return call_result.AuthorizePayload(
            id_tag_info={'status': AuthorizationStatus.accepted}
        )

    @on(Action.StartTransaction)
    async def on_start_transaction(
        self, connector_id, id_tag, meter_start, timestamp, **kwargs
    ):
        transaction_id = random.randint(100000, 999999)
        logger.info(
            f'Transaction started: {transaction_id} on CP {self.id} '
            f'connector {connector_id}, meter_start={meter_start}'
        )

        try:
            from asgiref.sync import sync_to_async
            await sync_to_async(self._handle_start_transaction)(
                connector_id, id_tag, meter_start, timestamp, transaction_id
            )
        except Exception as e:
            logger.error(f'Error handling start transaction: {e}')

        return call_result.StartTransactionPayload(
            transaction_id=transaction_id,
            id_tag_info={'status': AuthorizationStatus.accepted},
        )

    def _handle_start_transaction(
        self, connector_id, id_tag, meter_start, timestamp, transaction_id
    ):
        from apps.charging.models import ChargingSession
        from apps.stations.models import Connector

        try:
            session = ChargingSession.objects.filter(
                status=ChargingSession.StatusChoices.ACTIVE,
                connector__ocpp_connector_id=connector_id,
            ).first()

            if session:
                session.ocpp_transaction_id = transaction_id
                session.save(update_fields=['ocpp_transaction_id'])
                logger.info(
                    f'Updated session {session.pk} with OCPP transaction {transaction_id}'
                )
        except Exception as e:
            logger.error(f'Error in _handle_start_transaction: {e}')

    @on(Action.StopTransaction)
    async def on_stop_transaction(
        self, meter_stop, timestamp, transaction_id, **kwargs
    ):
        logger.info(
            f'Transaction stopped: {transaction_id}, meter_stop={meter_stop}'
        )

        try:
            from asgiref.sync import sync_to_async
            await sync_to_async(self._handle_stop_transaction)(
                meter_stop, timestamp, transaction_id
            )
        except Exception as e:
            logger.error(f'Error handling stop transaction: {e}')

        return call_result.StopTransactionPayload()

    def _handle_stop_transaction(self, meter_stop, timestamp, transaction_id):
        from apps.charging.models import ChargingSession
        from django.utils import timezone

        try:
            session = ChargingSession.objects.filter(
                ocpp_transaction_id=transaction_id,
                status=ChargingSession.StatusChoices.ACTIVE,
            ).first()

            if session:
                logger.info(
                    f'Session {session.pk} stopped via OCPP, '
                    f'meter_stop={meter_stop}'
                )
                # Actual session completion is handled by the API StopCharging endpoint
                # or the complete_expired_sessions task
        except Exception as e:
            logger.error(f'Error in _handle_stop_transaction: {e}')

    @on(Action.MeterValues)
    async def on_meter_values(
        self, connector_id, transaction_id, meter_value, **kwargs
    ):
        logger.debug(
            f'Meter values for CP {self.id} connector {connector_id} '
            f'transaction {transaction_id}'
        )

        try:
            from asgiref.sync import sync_to_async
            await sync_to_async(self._handle_meter_values)(
                connector_id, transaction_id, meter_value
            )
        except Exception as e:
            logger.error(f'Error handling meter values: {e}')

        return call_result.MeterValuesPayload()

    def _handle_meter_values(self, connector_id, transaction_id, meter_value):
        from apps.charging.models import ChargingSession
        from decimal import Decimal

        try:
            session = ChargingSession.objects.filter(
                ocpp_transaction_id=transaction_id,
                status=ChargingSession.StatusChoices.ACTIVE,
            ).first()

            if not session:
                return

            # Parse energy from meter values
            for mv in meter_value:
                for sv in mv.get('sampled_value', []):
                    measurand = sv.get('measurand', '')
                    value = sv.get('value', '0')
                    unit = sv.get('unit', '')

                    if measurand == 'Energy.Active.Import.Register' or measurand == '':
                        try:
                            energy = Decimal(str(value))
                            if unit == 'Wh':
                                energy = energy / 1000  # Convert to kWh
                            session.energy_kwh = energy
                            session.cost = energy * session.connector.price_per_kwh
                            session.save(update_fields=['energy_kwh', 'cost'])
                            logger.debug(
                                f'Session {session.pk}: energy={energy} kWh'
                            )
                        except (ValueError, Exception) as e:
                            logger.warning(f'Error parsing meter value: {e}')

        except Exception as e:
            logger.error(f'Error in _handle_meter_values: {e}')
