from django.db import models
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, permissions, viewsets, filters
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import (
    Hotel,
)
from .serializers import (
    VisaRequestSerializer,
    TransferRequestSerializer,
    TranslatorRequestSerializer,
    SimCardRequestSerializer,
    HotelSerializer,
    BookingSerializer, HotelImageSerializer,
)
from .permissions import IsOwner, HotelPermission, BookingPermission


class HotelViewSet(viewsets.ModelViewSet):
    """Mehmonxonalar"""
    queryset = Hotel.objects.all().order_by("name")
    serializer_class = HotelSerializer
    permission_classes = [HotelPermission]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "address"]

    @swagger_auto_schema(operation_summary="Mehmonxona yaratish", operation_description="Yangi mehmonxona qo'shish", tags=["hotels"])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Mehmonxona detali", operation_description="Bitta mehmonxona ma'lumotlari", tags=["hotels"])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Mehmonxonani yangilash", operation_description="Mehmonxona ma'lumotlarini yangilash", tags=["hotels"])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Mehmonxonani qisman yangilash", operation_description="Mehmonxona ma'lumotlarini qisman yangilash", tags=["hotels"])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Mehmonxonani o'chirish", operation_description="Mehmonxonani o'chirish", tags=["hotels"])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Mehmonxona rasmi yuklash",
        operation_description="Mehmonxonaga rasm biriktirish",
        tags=["hotels"],
        manual_parameters=[
            openapi.Parameter("image", openapi.IN_FORM, type=openapi.TYPE_FILE, description="Rasm fayli", required=True),
        ],
        responses={200: "Rasm yuklandi"},
    )
    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser], url_path="upload-image", url_name="upload_image")
    def upload_image(self, request, pk=None):
        hotel = self.get_object()
        serializer = HotelImageSerializer(hotel, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # to‘liq image URL qaytaradi
            return Response({"image": request.build_absolute_uri(serializer.data["image"])}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_summary="Mehmonxonalar ro'yxati",
        operation_description="Mehmonxonalar ro'yxati filtrlar bilan",
        tags=["hotels"],
        manual_parameters=[
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Qidirish"),
            openapi.Parameter("min_price", openapi.IN_QUERY, type=openapi.TYPE_NUMBER, description="Minimal narx"),
            openapi.Parameter("max_price", openapi.IN_QUERY, type=openapi.TYPE_NUMBER, description="Maksimal narx"),
            openapi.Parameter("stars", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Yulduzlar soni"),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifa"),
        ],
        responses={200: HotelSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                models.Q(name__icontains=search)
                | models.Q(address__icontains=search)
            )

        min_price = request.query_params.get("min_price")
        max_price = request.query_params.get("max_price")
        if min_price:
            qs = qs.filter(price_per_night__gte=min_price)
        if max_price:
            qs = qs.filter(price_per_night__lte=max_price)

        stars = request.query_params.get("stars")
        if stars:
            qs = qs.filter(stars=stars)

        page = int(request.query_params.get("page", 1))
        per_page = 10
        start = (page - 1) * per_page
        end = start + per_page

        serializer = self.get_serializer(qs[start:end], many=True, context={"request": request})
        return Response({
            "count": qs.count(),
            "page": page,
            "results": serializer.data
        })

class VisaCreateView(generics.CreateAPIView):
    serializer_class = VisaRequestSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        # Swagger schema generation uchun
        if getattr(self, 'swagger_fake_view', False):
            return VisaRequest.objects.none()
        return VisaRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        operation_summary="Visa so'rovi yaratish",
        operation_description="Yangi visa so'rovi yuborish",
        tags=["visa"],
        request_body=VisaRequestSerializer,
        responses={201: VisaRequestSerializer()},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class VisaRetrieveView(generics.RetrieveUpdateAPIView):
    serializer_class = VisaRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        # Swagger schema generation uchun
        if getattr(self, 'swagger_fake_view', False):
            return VisaRequest.objects.none()
        return VisaRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        operation_summary="Visa so'rovini olish",
        operation_description="Foydalanuvchining visa so'rovini olish",
        tags=["visa"],
        responses={200: VisaRequestSerializer()},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Visa so'rovini yangilash",
        operation_description="Visa so'rovini yangilash (tags, note)",
        tags=["visa"],
        request_body=VisaRequestSerializer,
        responses={200: VisaRequestSerializer()},
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Visa so'rovini to'liq yangilash",
        operation_description="Visa so'rovini to'liq yangilash",
        tags=["visa"],
        request_body=VisaRequestSerializer,
        responses={200: VisaRequestSerializer()},
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)


class TransferCreateView(generics.CreateAPIView):
    serializer_class = TransferRequestSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        # Swagger schema generation uchun
        if getattr(self, 'swagger_fake_view', False):
            return TransferRequest.objects.none()
        return TransferRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        operation_summary="Transfer so'rovi yaratish",
        operation_description="Yangi transfer so'rovi yuborish",
        tags=["transfer"],
        request_body=TransferRequestSerializer,
        responses={201: TransferRequestSerializer()},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class TransferRetrieveView(generics.RetrieveUpdateAPIView):
    serializer_class = TransferRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        # Swagger schema generation uchun
        if getattr(self, 'swagger_fake_view', False):
            return TransferRequest.objects.none()
        return TransferRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        operation_summary="Transfer so'rovini olish",
        operation_description="Foydalanuvchining transfer so'rovini olish",
        tags=["transfer"],
        responses={200: TransferRequestSerializer()},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Transfer so'rovini yangilash",
        operation_description="Transfer so'rovini yangilash (tags)",
        tags=["transfer"],
        request_body=TransferRequestSerializer,
        responses={200: TransferRequestSerializer()},
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class BookingViewSet(viewsets.ModelViewSet):
    """Mehmonxona bronlari"""
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, BookingPermission]

    def get_queryset(self):
        # Swagger schema generation uchun
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()

        user = self.request.user
        if user.role in ["admin", "superadmin", "operator"]:
            return Booking.objects.all()
        return Booking.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @swagger_auto_schema(operation_summary="Bronlar ro'yxati", operation_description="Barcha bronlar", tags=["bookings"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Bron yaratish", operation_description="Yangi bron qo'shish", tags=["bookings"])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Bron detali", operation_description="Bitta bron ma'lumotlari", tags=["bookings"])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Bronni yangilash", operation_description="Bron ma'lumotlarini yangilash", tags=["bookings"])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Bronni qisman yangilash", operation_description="Bron ma'lumotlarini qisman yangilash", tags=["bookings"])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Bronni o'chirish", operation_description="Bronni o'chirish", tags=["bookings"])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class TranslatorCreateView(generics.CreateAPIView):
    serializer_class = TranslatorRequestSerializer

    def get_queryset(self):
        # Swagger schema generation uchun
        if getattr(self, 'swagger_fake_view', False):
            return TranslatorRequest.objects.none()
        return TranslatorRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        operation_summary="Tarjimon so'rovi yaratish",
        operation_description="Yangi tarjimon so'rovi yuborish",
        tags=["translator"],
        request_body=TranslatorRequestSerializer,
        responses={201: TranslatorRequestSerializer()},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class TranslatorRetrieveView(generics.RetrieveUpdateAPIView):
    serializer_class = TranslatorRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        # Swagger schema generation uchun
        if getattr(self, 'swagger_fake_view', False):
            return TranslatorRequest.objects.none()
        return TranslatorRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        operation_summary="Tarjimon so'rovini olish",
        operation_description="Foydalanuvchining tarjimon so'rovini olish",
        tags=["translator"],
        responses={200: TranslatorRequestSerializer()},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Tarjimon so'rovini yangilash",
        operation_description="Tarjimon so'rovini yangilash (tags, requirements)",
        tags=["translator"],
        request_body=TranslatorRequestSerializer,
        responses={200: TranslatorRequestSerializer()},
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class SimCardCreateView(generics.CreateAPIView):
    serializer_class = SimCardRequestSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        # Swagger schema generation uchun
        if getattr(self, 'swagger_fake_view', False):
            return SimCardRequest.objects.none()
        return SimCardRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        operation_summary="SIM karta buyurtmasi yaratish",
        operation_description="Yangi SIM karta buyurtmasi yuborish",
        tags=["simcard"],
        request_body=SimCardRequestSerializer,
        responses={201: SimCardRequestSerializer()},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class SimCardRetrieveView(generics.RetrieveUpdateAPIView):
    serializer_class = SimCardRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        # Swagger schema generation uchun
        if getattr(self, 'swagger_fake_view', False):
            return SimCardRequest.objects.none()
        return SimCardRequest.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        operation_summary="SIM karta buyurtmasini olish",
        operation_description="Foydalanuvchining SIM karta buyurtmasini olish",
        tags=["simcard"],
        responses={200: SimCardRequestSerializer()},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="SIM karta buyurtmasini yangilash",
        operation_description="SIM karta buyurtmasini yangilash (tags, note)",
        tags=["simcard"],
        request_body=SimCardRequestSerializer,
        responses={200: SimCardRequestSerializer()},
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db import transaction

from applications.models import Patient
from core.models import Tag
from services.models import (
    VisaRequest, TransferRequest, TranslatorRequest, SimCardRequest, Booking
)
from services.serializers import (
    VisaRequestSerializer, TransferRequestSerializer,
    TranslatorRequestSerializer, SimCardRequestSerializer, BookingSerializer
)


# ===========================================================
# BEMOR O'Z BUYURTMALARINI KO'RISH (/orders/me)
# ===========================================================
class OrdersMeView(APIView):
    """Bemor (patient) o‘zining buyurtmalarini ko‘rish uchun."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Bemorga tegishli buyurtmalar",
        operation_description="Login bo'lgan bemor o'ziga tegishli buyurtmalarni ko'radi",
        responses={200: "Bemorning barcha buyurtmalari"},
        tags=["orders"]
    )
    def get(self, request):
        user = request.user

        if user.role not in ["user", "patient"]:
            return Response(
                {"detail": "Faqat bemorlar uchun."},
                status=status.HTTP_403_FORBIDDEN
            )

        data = {
            "visas": VisaRequestSerializer(
                VisaRequest.objects.filter(user=user),
                many=True, context={"request": request}
            ).data,
            "transfers": TransferRequestSerializer(
                TransferRequest.objects.filter(user=user),
                many=True, context={"request": request}
            ).data,
            "translators": TranslatorRequestSerializer(
                TranslatorRequest.objects.filter(user=user),
                many=True, context={"request": request}
            ).data,
            "simcards": SimCardRequestSerializer(
                SimCardRequest.objects.filter(user=user),
                many=True, context={"request": request}
            ).data,
            "bookings": BookingSerializer(
                Booking.objects.filter(user=user),
                many=True, context={"request": request}
            ).data,
        }

        return Response(data, status=status.HTTP_200_OK)


# ===========================================================
# ADMIN / OPERATOR / PARTNER uchun ORDERLAR (/orders/)
# ===========================================================
class OrdersListView(APIView):
    """Operator, admin, superadmin yoki partner barcha buyurtmalarni ko‘rish uchun."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Barcha buyurtmalar ro'yxati",
        operation_description="Admin, operator, partner barcha buyurtmalarni ko'ra oladi",
        manual_parameters=[
            openapi.Parameter("patient_id", openapi.IN_QUERY, description="Bemor ID", type=openapi.TYPE_INTEGER, required=False)
        ],
        responses={200: "Barcha buyurtmalar"},
        tags=["orders"]
    )
    def get(self, request):
        user = request.user
        patient_id = request.query_params.get("patient_id")

        # ✅ Ruxsat berilgan rollar
        allowed_roles = ["admin", "superadmin", "operator", "partner"]
        if user.role not in allowed_roles:
            return Response(
                {"detail": "Faqat operator, admin, superadmin yoki partner uchun."},
                status=status.HTTP_403_FORBIDDEN
            )

        # ✅ patient_id bo‘lsa – filtr qilamiz
        if patient_id:
            try:
                patient = Patient.objects.get(id=patient_id)
                user_obj = patient.created_by
            except Patient.DoesNotExist:
                return Response(
                    {"detail": f"Bemor ID {patient_id} topilmadi."},
                    status=status.HTTP_404_NOT_FOUND
                )

            visas = VisaRequest.objects.filter(user=user_obj)
            transfers = TransferRequest.objects.filter(user=user_obj)
            translators = TranslatorRequest.objects.filter(user=user_obj)
            simcards = SimCardRequest.objects.filter(user=user_obj)
            bookings = Booking.objects.filter(user=user_obj)
        else:
            visas = VisaRequest.objects.all()
            transfers = TransferRequest.objects.all()
            translators = TranslatorRequest.objects.all()
            simcards = SimCardRequest.objects.all()
            bookings = Booking.objects.all()

        data = {
            "visas": VisaRequestSerializer(visas, many=True, context={"request": request}).data,
            "transfers": TransferRequestSerializer(transfers, many=True, context={"request": request}).data,
            "translators": TranslatorRequestSerializer(translators, many=True, context={"request": request}).data,
            "simcards": SimCardRequestSerializer(simcards, many=True, context={"request": request}).data,
            "bookings": BookingSerializer(bookings, many=True, context={"request": request}).data,
        }

        return Response(data, status=status.HTTP_200_OK)


# ===========================================================
# Bitta bemorning ORDERLARI (/orders/{id}/)
# ===========================================================
class PatientOrdersDetailView(APIView):
    """Bitta bemorning barcha buyurtmalarini olish (id bo‘yicha)."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Bemor buyurtmalari",
        operation_description="Bitta bemorning barcha buyurtmalari ID orqali",
        responses={200: "Bemorning barcha buyurtmalari"},
        tags=["orders"]
    )
    def get(self, request, id):
        user = request.user

        allowed_roles = ["admin", "superadmin", "operator", "partner"]
        if user.role not in allowed_roles:
            return Response(
                {"detail": "Faqat operator, admin, superadmin yoki partner uchun."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            patient = Patient.objects.get(id=id)
            user_obj = patient.created_by
        except Patient.DoesNotExist:
            return Response(
                {"detail": f"Bemor ID {id} topilmadi."},
                status=status.HTTP_404_NOT_FOUND
            )

        data = {
            "visas": VisaRequestSerializer(
                VisaRequest.objects.filter(user=user_obj),
                many=True, context={"request": request}
            ).data,
            "transfers": TransferRequestSerializer(
                TransferRequest.objects.filter(user=user_obj),
                many=True, context={"request": request}
            ).data,
            "translators": TranslatorRequestSerializer(
                TranslatorRequest.objects.filter(user=user_obj),
                many=True, context={"request": request}
            ).data,
            "simcards": SimCardRequestSerializer(
                SimCardRequest.objects.filter(user=user_obj),
                many=True, context={"request": request}
            ).data,
            "bookings": BookingSerializer(
                Booking.objects.filter(user=user_obj),
                many=True, context={"request": request}
            ).data,
        }

        return Response(data, status=status.HTTP_200_OK)
