import asyncio
import logging

import websockets

from .charge_point import ChargePoint

logger = logging.getLogger(__name__)

connected_charge_points = {}


async def on_connect(websocket, path):
    """Handle new charge point WebSocket connection."""
    charge_point_id = path.strip('/')
    cp = ChargePoint(charge_point_id, websocket)
    connected_charge_points[charge_point_id] = cp
    logger.info(f'Charge point connected: {charge_point_id}')
    try:
        await cp.start()
    finally:
        if charge_point_id in connected_charge_points:
            del connected_charge_points[charge_point_id]
        logger.info(f'Charge point disconnected: {charge_point_id}')


async def send_remote_start(charge_point_id, connector_id, id_tag):
    """Send RemoteStartTransaction command to charge point."""
    if charge_point_id in connected_charge_points:
        cp = connected_charge_points[charge_point_id]
        from ocpp.v16 import call
        request = call.RemoteStartTransactionPayload(
            connector_id=connector_id,
            id_tag=id_tag,
        )
        try:
            response = await cp.call(request)
            logger.info(
                f'RemoteStartTransaction to {charge_point_id}: {response}'
            )
            return response
        except Exception as e:
            logger.error(
                f'Error sending RemoteStartTransaction to {charge_point_id}: {e}'
            )
            return None
    else:
        logger.warning(
            f'Charge point {charge_point_id} not connected, '
            f'cannot send RemoteStartTransaction'
        )
        return None


async def send_remote_stop(charge_point_id, transaction_id):
    """Send RemoteStopTransaction command to charge point."""
    if charge_point_id in connected_charge_points:
        cp = connected_charge_points[charge_point_id]
        from ocpp.v16 import call
        request = call.RemoteStopTransactionPayload(
            transaction_id=transaction_id,
        )
        try:
            response = await cp.call(request)
            logger.info(
                f'RemoteStopTransaction to {charge_point_id}: {response}'
            )
            return response
        except Exception as e:
            logger.error(
                f'Error sending RemoteStopTransaction to {charge_point_id}: {e}'
            )
            return None
    else:
        logger.warning(
            f'Charge point {charge_point_id} not connected, '
            f'cannot send RemoteStopTransaction'
        )
        return None


def get_connected_charge_points():
    """Return list of currently connected charge point IDs."""
    return list(connected_charge_points.keys())


def run_server(host='0.0.0.0', port=9000):
    """Start the OCPP WebSocket server."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    server = websockets.serve(
        on_connect,
        host,
        port,
        subprotocols=['ocpp1.6'],
    )

    loop.run_until_complete(server)
    logger.info(f'OCPP server started on {host}:{port}')
    loop.run_forever()
