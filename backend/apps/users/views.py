import logging

from django.conf import settings
from rest_framework import status, generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, OTPCode, FavoriteStation
from .serializers import (
    SendOTPSerializer,
    VerifyOTPSerializer,
    UserSerializer,
    UserUpdateSerializer,
    FavoriteStationSerializer,
)

logger = logging.getLogger(__name__)


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class SendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']
        otp = OTPCode.generate(phone)

        response_data = {'message': 'OTP отправлен'}

        if settings.DEBUG:
            # In development, return the code in the response
            response_data['code'] = otp.code
            logger.debug(f'OTP for {phone}: {otp.code}')
        else:
            # In production, send SMS via provider
            # TODO: Integrate with SMS provider (e.g., SMSAero, SMSC)
            logger.info(f'OTP generated for {phone}, would send SMS in production')

        return Response(response_data, status=status.HTTP_200_OK)


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']
        code = serializer.validated_data['code']

        phone_str = str(phone)

        try:
            otp = OTPCode.objects.filter(
                phone=phone_str,
                code=code,
                is_used=False,
            ).latest('created_at')
        except OTPCode.DoesNotExist:
            return Response(
                {'error': 'Неверный код'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not otp.is_valid():
            return Response(
                {'error': 'Код истёк или уже использован'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp.is_used = True
        otp.save()

        user, created = User.objects.get_or_create(phone=phone)
        if not user.is_active:
            return Response(
                {'error': 'Аккаунт заблокирован'},
                status=status.HTTP_403_FORBIDDEN,
            )

        tokens = get_tokens_for_user(user)

        return Response({
            'tokens': tokens,
            'user': UserSerializer(user).data,
            'is_new_user': created,
        }, status=status.HTTP_200_OK)


class ProfileView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response(
            {'message': 'Аккаунт деактивирован'},
            status=status.HTTP_200_OK,
        )


class FavoriteStationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FavoriteStationSerializer

    def get_queryset(self):
        return FavoriteStation.objects.filter(
            user=self.request.user
        ).select_related('station').prefetch_related('station__connectors')


class FavoriteStationToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, station_id):
        from apps.stations.models import Station
        try:
            station = Station.objects.get(pk=station_id)
        except Station.DoesNotExist:
            return Response(
                {'error': 'Станция не найдена'},
                status=status.HTTP_404_NOT_FOUND,
            )

        favorite, created = FavoriteStation.objects.get_or_create(
            user=request.user,
            station=station,
        )

        if created:
            return Response(
                {'message': 'Добавлено в избранное'},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {'message': 'Уже в избранном'},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, station_id):
        deleted, _ = FavoriteStation.objects.filter(
            user=request.user,
            station_id=station_id,
        ).delete()

        if deleted:
            return Response(
                {'message': 'Удалено из избранного'},
                status=status.HTTP_200_OK,
            )
        return Response(
            {'error': 'Не найдено в избранном'},
            status=status.HTTP_404_NOT_FOUND,
        )
