import logging

from channels.generic.websocket import WebsocketConsumer

logger = logging.getLogger(__name__)


class OCPPConsumer(WebsocketConsumer):
    """
    Django Channels WebSocket consumer for OCPP connections.
    This provides the Channels-based ASGI entry point.
    The actual OCPP protocol handling is done by the standalone
    central_system.py server running on port 9000.
    """

    def connect(self):
        self.charge_point_id = self.scope['url_route']['kwargs']['charge_point_id']
        self.accept(subprotocol='ocpp1.6')
        logger.info(f'OCPP WebSocket connected: {self.charge_point_id}')

    def disconnect(self, close_code):
        logger.info(
            f'OCPP WebSocket disconnected: {self.charge_point_id}, '
            f'code={close_code}'
        )

    def receive(self, text_data=None, bytes_data=None):
        """
        Receive OCPP message and process it.
        In production, this would integrate with the OCPP library.
        """
        if text_data:
            logger.debug(
                f'OCPP message from {self.charge_point_id}: {text_data[:100]}'
            )
            # For full OCPP support, integrate with ChargePoint handler here
            # For now, just acknowledge
