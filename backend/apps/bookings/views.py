import logging

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking
from .serializers import BookingSerializer, CreateBookingSerializer

logger = logging.getLogger(__name__)


class BookingListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateBookingSerializer
        return BookingSerializer

    def get_queryset(self):
        return Booking.objects.filter(
            user=self.request.user
        ).select_related('connector__station').order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = CreateBookingSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()

        # Send push notification
        try:
            from apps.notifications.services import NotificationService
            NotificationService.send_booking_created(request.user, booking)
        except Exception as e:
            logger.warning(f'Failed to send booking notification: {e}')

        return Response(
            BookingSerializer(booking).data,
            status=status.HTTP_201_CREATED,
        )


class CancelBookingView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            booking = Booking.objects.get(
                pk=pk,
                user=request.user,
                status=Booking.StatusChoices.ACTIVE,
            )
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Активная бронь не найдена'},
                status=status.HTTP_404_NOT_FOUND,
            )

        booking.cancel()

        return Response(
            {'message': 'Бронь отменена'},
            status=status.HTTP_200_OK,
        )
