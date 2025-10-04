from rest_framework import viewsets, generics, permissions, filters, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.response import Response
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
from rest_framework.permissions import IsAuthenticated


# ----------------- Visa -----------------
class VisaCreateView(generics.CreateAPIView):
    serializer_class = VisaRequestSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return VisaRequest.objects.none()
        return VisaRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        tags=["Visa"],
        operation_description="Foydalanuvchi yangi visa so‘rovi yuboradi.",
        request_body=VisaRequestSerializer,
        responses={201: openapi.Response("Created", VisaRequestSerializer()), 400: "Bad Request", 401: "Unauthorized"},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class VisaRetrieveView(generics.RetrieveAPIView):
    serializer_class = VisaRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return VisaRequest.objects.none()
        return VisaRequest.objects.filter(user=self.request.user)


# ----------------- Transfer -----------------
class TransferCreateView(generics.CreateAPIView):
    serializer_class = TransferRequestSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TransferRequest.objects.none()
        return TransferRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        tags=["Transfer"],
        operation_description="Foydalanuvchi yangi transfer so‘rovi yuboradi.",
        request_body=TransferRequestSerializer,
        responses={201: openapi.Response("Created", TransferRequestSerializer()), 400: "Bad Request", 401: "Unauthorized"},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class TransferRetrieveView(generics.RetrieveAPIView):
    serializer_class = TransferRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TransferRequest.objects.none()
        return TransferRequest.objects.filter(user=self.request.user)


# ----------------- Booking -----------------
class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, BookingPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Booking.objects.none()

        user = self.request.user
        role = getattr(user, "role", None)
        if role in ["admin", "superadmin", "operator"]:
            return Booking.objects.all()
        return Booking.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ----------------- Hotel -----------------
class HotelViewSet(viewsets.ModelViewSet):
    queryset = Hotel.objects.all()
    serializer_class = HotelSerializer
    permission_classes = [HotelPermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "address"]


# ----------------- Translator -----------------
class TranslatorCreateView(generics.CreateAPIView):
    serializer_class = TranslatorRequestSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TranslatorRequest.objects.none()
        return TranslatorRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        tags=["Translator"],
        operation_description="Foydalanuvchi yangi tarjimon so‘rovi yuboradi.",
        request_body=TranslatorRequestSerializer,
        responses={201: openapi.Response("Created", TranslatorRequestSerializer()), 400: "Bad Request", 401: "Unauthorized"},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class TranslatorRetrieveView(generics.RetrieveAPIView):
    serializer_class = TranslatorRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TranslatorRequest.objects.none()
        return TranslatorRequest.objects.filter(user=self.request.user)


# ----------------- SimCard -----------------
class SimCardCreateView(generics.CreateAPIView):
    serializer_class = SimCardRequestSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SimCardRequest.objects.none()
        return SimCardRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        tags=["SimCard"],
        operation_description="Foydalanuvchi yangi SIM karta buyurtmasi qiladi.",
        request_body=SimCardRequestSerializer,
        responses={201: openapi.Response("Created", SimCardRequestSerializer()), 400: "Bad Request", 401: "Unauthorized"},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class SimCardRetrieveView(generics.RetrieveAPIView):
    serializer_class = SimCardRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SimCardRequest.objects.none()
        return SimCardRequest.objects.filter(user=self.request.user)


# ----------------- Orders -----------------
class OrdersMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if getattr(user, "role", None) not in ["user", "patient"]:
            return Response({"detail": "Faqat bemorlar uchun."}, status=status.HTTP_403_FORBIDDEN)

        data = {
            "visas": VisaRequestSerializer(VisaRequest.objects.filter(user=user), many=True).data,
            "transfers": TransferRequestSerializer(TransferRequest.objects.filter(user=user), many=True).data,
            "translators": TranslatorRequestSerializer(TranslatorRequest.objects.filter(user=user), many=True).data,
            "simcards": SimCardRequestSerializer(SimCardRequest.objects.filter(user=user), many=True).data,
            "bookings": BookingSerializer(Booking.objects.filter(user=user), many=True).data,
        }
        return Response(data)


class OrdersListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if getattr(user, "role", None) not in ["admin", "superadmin", "operator"]:
            return Response({"detail": "Faqat operator/admin/superadmin uchun."}, status=status.HTTP_403_FORBIDDEN)

        data = {
            "visas": VisaRequestSerializer(VisaRequest.objects.all(), many=True).data,
            "transfers": TransferRequestSerializer(TransferRequest.objects.all(), many=True).data,
            "translators": TranslatorRequestSerializer(TranslatorRequest.objects.all(), many=True).data,
            "simcards": SimCardRequestSerializer(SimCardRequest.objects.all(), many=True).data,
            "bookings": BookingSerializer(Booking.objects.all(), many=True).data,
        }
        return Response(data)
