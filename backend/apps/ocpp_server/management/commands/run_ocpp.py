from django.core.management.base import BaseCommand

from apps.ocpp_server.central_system import run_server


class Command(BaseCommand):
    help = 'Start OCPP 1.6 WebSocket server'

    def add_arguments(self, parser):
        parser.add_argument(
            '--host',
            default='0.0.0.0',
            help='Host to bind to (default: 0.0.0.0)',
        )
        parser.add_argument(
            '--port',
            type=int,
            default=9000,
            help='Port to listen on (default: 9000)',
        )

    def handle(self, *args, **options):
        host = options['host']
        port = options['port']
        self.stdout.write(
            self.style.SUCCESS(f'Starting OCPP server on {host}:{port}')
        )
        run_server(host, port)
