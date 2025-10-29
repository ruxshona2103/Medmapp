from django.db import models
from rest_framework.decorators import action
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
    BookingSerializer, HotelImageSerializer,
)
from .permissions import IsOwner, HotelPermission, BookingPermission


class HotelViewSet(viewsets.ModelViewSet):
    """
    Mehmonxonalar ro'yxati.
    Filtrlar:
    - search: nomi yoki manzili bo‘yicha
    - min_price, max_price: narx oralig‘ida
    - stars: yulduzlar soni bo‘yicha
    """
    queryset = Hotel.objects.all().order_by("name")
    serializer_class = HotelSerializer
    permission_classes = [HotelPermission]
    parser_classes = [MultiPartParser, FormParser]  # Rasm upload uchun
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "address"]

    # 🔽 Rasm yuklash uchun endpoint (boshqa maydonlarsiz)
    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
        url_path="upload-image",
        url_name="upload_image",
    )
    @swagger_auto_schema(
        operation_description="Faqat mehmonxona rasmi yuklash uchun.",
        tags=["hotels"],
        manual_parameters=[
            openapi.Parameter(
                "image",
                openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description="Yangi rasm faylini yuklash (faqat image).",
                required=True,
            ),
        ],
        responses={200: openapi.Response("Image uploaded successfully")},
    )
    def upload_image(self, request, pk=None):
        hotel = self.get_object()
        serializer = HotelImageSerializer(hotel, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # to‘liq image URL qaytaradi
            return Response({"image": request.build_absolute_uri(serializer.data["image"])}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=["hotels"],
        operation_description="Mehmonxonalar ro'yxati (filtrlar: search, min_price, max_price, stars).",
        manual_parameters=[
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Mehmonxona nomi yoki manzili bo‘yicha qidirish"),
            openapi.Parameter("min_price", openapi.IN_QUERY, type=openapi.TYPE_NUMBER, description="Minimal narx (masalan: 50)"),
            openapi.Parameter("max_price", openapi.IN_QUERY, type=openapi.TYPE_NUMBER, description="Maksimal narx (masalan: 200)"),
            openapi.Parameter("stars", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Yulduzlar soni (masalan: 3, 4, 5)"),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Sahifa raqami (pagination uchun)"),
        ],
        responses={200: openapi.Response("OK", HotelSerializer(many=True))},
    )
    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()

        # 🔍 Search — name va address bo‘yicha
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                models.Q(name__icontains=search)
                | models.Q(address__icontains=search)
            )

        # 💰 Price filter
        min_price = request.query_params.get("min_price")
        max_price = request.query_params.get("max_price")
        if min_price:
            qs = qs.filter(price_per_night__gte=min_price)
        if max_price:
            qs = qs.filter(price_per_night__lte=max_price)

        # ⭐ Stars filter
        stars = request.query_params.get("stars")
        if stars:
            qs = qs.filter(stars=stars)

        # 🔢 Pagination (oddiy)
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

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from applications.models import Patient
from services.models import (
    VisaRequest, TransferRequest, TranslatorRequest, SimCardRequest, Booking
)
from services.serializers import (
    VisaRequestSerializer, TransferRequestSerializer,
    TranslatorRequestSerializer, SimCardRequestSerializer, BookingSerializer
)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from applications.models import Patient
from services.models import (
    VisaRequest, TransferRequest, TranslatorRequest, SimCardRequest, Booking
)
from services.serializers import (
    VisaRequestSerializer, TransferRequestSerializer,
    TranslatorRequestSerializer, SimCardRequestSerializer, BookingSerializer
)


# ===========================================================
# 1️⃣ BEMOR O‘Z BUYURTMALARINI KO‘RISH (/orders/me)
# ===========================================================
class OrdersMeView(APIView):
    """Bemor (patient) o‘zining buyurtmalarini ko‘rish uchun."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="🧍‍♀️ Bemorga tegishli buyurtmalar (visa, simcard, booking va h.k.)",
        operation_description="Login bo‘lgan bemor faqat o‘ziga tegishli buyurtmalarni ko‘radi.",
        responses={200: "Bemorning barcha buyurtmalari"}
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
# 2️⃣ ADMIN / OPERATOR / PARTNER uchun ORDERLAR (/orders/)
# ===========================================================
class OrdersListView(APIView):
    """Operator, admin, superadmin yoki partner barcha buyurtmalarni ko‘rish uchun."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="📦 Barcha buyurtmalar ro‘yxati (admin/operator/partner)",
        operation_description=(
            "Admin, operator, superadmin yoki partner barcha bemorlarning buyurtmalarini ko‘ra oladi.\n\n"
            "Query parametrlari:\n"
            "- **patient_id**: faqat shu bemorning buyurtmalarini ko‘rsatadi\n\n"
            "**Misol:** `/orders/?patient_id=3` → Bemor ID=3 ning barcha buyurtmalari"
        ),
        manual_parameters=[
            openapi.Parameter(
                "patient_id",
                openapi.IN_QUERY,
                description="Bemor ID (shu bemorning buyurtmalarini ko‘rish uchun)",
                type=openapi.TYPE_INTEGER,
                required=False
            )
        ],
        responses={200: "Barcha buyurtmalar (visa, simcard, booking va h.k.)"}
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
# 3️⃣ Bitta bemorning ORDERLARI (/orders/{id}/)
# ===========================================================
class PatientOrdersDetailView(APIView):
    """Bitta bemorning barcha buyurtmalarini olish (id bo‘yicha)."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="👤 Bemor buyurtmalari (ID orqali)",
        operation_description=(
            "Bitta bemorning barcha buyurtmalari (visa, booking, simcard, transfer, translator) qaytariladi.\n\n"
            "**Misol:** `/orders/5/` → Bemor ID=5 ning barcha buyurtmalari"
        ),
        responses={200: "Bemorning barcha buyurtmalari"}
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
