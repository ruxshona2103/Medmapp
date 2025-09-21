from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, permissions, viewsets, filters
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import (
    VisaRequest,
    TransferRequest,
    TranslatorRequest,
    SimCardRequest,
    Hotel,
    Booking,
)
from .serializers import (
    VisaRequestSerializer,
    TransferRequestSerializer,
    TranslatorRequestSerializer,
    SimCardRequestSerializer,
    HotelSerializer,
    BookingSerializer,
)
from .permissions import IsOwner, HotelPermission, BookingPermission


class VisaCreateView(generics.CreateAPIView):
    serializer_class = VisaRequestSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        return VisaRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        tags=["Visa"],
        operation_description="Foydalanuvchi yangi visa so‘rovi yuboradi.",
        request_body=VisaRequestSerializer,  # yoki VisaRequestSerializer()
        responses={
            201: openapi.Response("Created", VisaRequestSerializer()),
            400: "Bad Request",
            401: "Unauthorized",
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class VisaRetrieveView(generics.RetrieveAPIView):
    serializer_class = VisaRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return VisaRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        tags=["Visa"],
        operation_description="Foydalanuvchining o‘ziga tegishli visa so‘rovini olish.",
        responses={
            200: openapi.Response("OK", VisaRequestSerializer()),
            401: "Unauthorized",
            404: "Not Found",
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class TransferCreateView(generics.CreateAPIView):
    serializer_class = TransferRequestSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        return TransferRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        tags=["Transfer"],
        operation_description="Foydalanuvchi yangi transfer so‘rovi yuboradi.",
        request_body=TransferRequestSerializer,
        responses={
            201: openapi.Response("Created", TransferRequestSerializer()),
            400: "Bad Request",
            401: "Unauthorized",
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class TransferRetrieveView(generics.RetrieveAPIView):
    serializer_class = TransferRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return TransferRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        tags=["Transfer"],
        operation_description="Foydalanuvchining transfer so‘rovini olish.",
        responses={
            200: openapi.Response("OK", TransferRequestSerializer()),
            401: "Unauthorized",
            404: "Not Found",
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, BookingPermission]

    def get_queryset(self):
        user = self.request.user
        if user.role in ["admin", "superadmin", "operator"]:
            return Booking.objects.all()
        return Booking.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class HotelViewSet(viewsets.ModelViewSet):
    queryset = Hotel.objects.all()
    serializer_class = HotelSerializer
    permission_classes = [HotelPermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "address"]


class TranslatorCreateView(generics.CreateAPIView):
    serializer_class = TranslatorRequestSerializer

    def get_queryset(self):
        return TranslatorRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        tags=["Translator"],
        operation_description="Foydalanuvchi yangi tarjimon so‘rovi yuboradi.",
        request_body=TranslatorRequestSerializer,
        responses={
            201: openapi.Response("Created", TranslatorRequestSerializer()),
            400: "Bad Request",
            401: "Unauthorized",
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class TranslatorRetrieveView(generics.RetrieveAPIView):
    serializer_class = TranslatorRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return TranslatorRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        tags=["Translator"],
        operation_description="Foydalanuvchining tarjimon so‘rovini olish.",
        responses={
            200: openapi.Response("OK", TranslatorRequestSerializer()),
            401: "Unauthorized",
            404: "Not Found",
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SimCardCreateView(generics.CreateAPIView):
    serializer_class = SimCardRequestSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        return SimCardRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        tags=["SimCard"],
        operation_description="Foydalanuvchi yangi SIM karta buyurtmasi qiladi.",
        request_body=SimCardRequestSerializer,
        responses={
            201: openapi.Response("Created", SimCardRequestSerializer()),
            400: "Bad Request",
            401: "Unauthorized",
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class SimCardRetrieveView(generics.RetrieveAPIView):
    serializer_class = SimCardRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return SimCardRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        tags=["SimCard"],
        operation_description="Foydalanuvchining SIM karta buyurtmasini olish.",
        responses={
            200: openapi.Response("OK", SimCardRequestSerializer()),
            401: "Unauthorized",
            404: "Not Found",
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class OrdersMeView(APIView):
    """
    Bemor (patient) o'z buyurtma bergan barcha servicelarni ko'rish uchun.
    URL: /orders/me (GET)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # Faqat patient roli uchun (agar roli 'user' yoki 'patient' bo'lsa)
        if user.role not in ["user", "patient"]:  # Rolni loyihangizga moslashtiring
            return Response(
                {"detail": "Faqat bemorlar uchun."}, status=status.HTTP_403_FORBIDDEN
            )

        data = {
            "visas": VisaRequestSerializer(
                VisaRequest.objects.filter(user=user), many=True
            ).data,
            "transfers": TransferRequestSerializer(
                TransferRequest.objects.filter(user=user), many=True
            ).data,
            "translators": TranslatorRequestSerializer(
                TranslatorRequest.objects.filter(user=user), many=True
            ).data,
            "simcards": SimCardRequestSerializer(
                SimCardRequest.objects.filter(user=user), many=True
            ).data,
            "bookings": BookingSerializer(
                Booking.objects.filter(user=user), many=True
            ).data,
        }
        return Response(data)


class OrdersListView(APIView):
    """
    Operator/admin/superadmin barcha buyurtmalarni ko'rish uchun.
    URL: /orders/ (GET)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role not in ["admin", "superadmin", "operator"]:
            return Response(
                {"detail": "Faqat operator/admin/superadmin uchun."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = {
            "visas": VisaRequestSerializer(VisaRequest.objects.all(), many=True).data,
            "transfers": TransferRequestSerializer(
                TransferRequest.objects.all(), many=True
            ).data,
            "translators": TranslatorRequestSerializer(
                TranslatorRequest.objects.all(), many=True
            ).data,
            "simcards": SimCardRequestSerializer(
                SimCardRequest.objects.all(), many=True
            ).data,
            "bookings": BookingSerializer(Booking.objects.all(), many=True).data,
        }
        return Response(data)
