from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import generics, permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.views import APIView   # APIView uchun
from rest_framework.exceptions import PermissionDenied  # PermissionDenied uchun

from applications.models import Application, ApplicationHistory, Document
from applications.permissions import IsAdminOrOperatorOrReadOnly
from applications.serializers import ApplicationSerializer, DocumentSerializer
from stages.models import Stage



class ApplicationCreateView(generics.CreateAPIView):
    """Bemor yangi arizasini yuboradi"""
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(patient=self.request.user)


class ApplicationStatusView(generics.RetrieveAPIView):
    """Bemor oxirgi arizani statusini korishi mumkun bo'ladi"""
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return Application.objects.filter(patient=self.request.user).latest("created_at")

class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOperatorOrReadOnly]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name="stage",
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                required=False,
                description="Stage bo'yicha filter (Stage ID)"
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Application.objects.none()

        user = self.request.user
        if not user.is_authenticated:
            return Application.objects.none()

        if getattr(user, 'role', None) == "user":
            queryset = Application.objects.filter(patient=user)
        else:
            queryset = Application.objects.all()

        stage_id = self.request.query_params.get('stage')
        if stage_id:
            queryset = queryset.filter(stage__id=stage_id)  # ForeignKey bo'lsa __id ishlatamiz

        return queryset.prefetch_related('documents', 'history')

class DocumentCreateView(generics.CreateAPIView):
    """
    Muayyan bir arizaga hujjat (fayl) yuklash uchun.
    URL manzilida application_id bo'lishi kerak.
    Masalan: /api/applications/12/documents/
    """
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    # 1-QADAM: Fayl qabul qilish uchun parserlarni qo'shamiz
    parser_classes = [MultiPartParser, FormParser]

    # 2-QADAM: Swagger'ga fayl yuklash formasini chizishni buyuramiz
    @swagger_auto_schema(
        operation_description="Tanlangan arizaga yangi hujjat (fayl) yuklash.",
        manual_parameters=[
            openapi.Parameter(
                name="file",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="Tizimga yuklanadigan hujjat"
            ),
            openapi.Parameter(
                name="description", # DocumentSerializer'da description maydoni bo'lsa
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False,
                description="Hujjat uchun qisqa izoh"
            ),
        ],
        request_body=None,
        responses={ 201: DocumentSerializer, 404: "Ariza topilmadi" }
    )
    def post(self, request, *args, **kwargs):
        """Faylni qabul qilib olib, uni saqlaydi."""
        return self.create(request, *args, **kwargs)

    class DocumentCreateView(generics.CreateAPIView):
    # """
    # Muayyan bir arizaga hujjat (fayl) yuklash uchun.
    # URL manzilida application_id bo'lishi kerak.
    # """
      serializer_class = DocumentSerializer
      permission_classes = [permissions.IsAuthenticated]
      parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        # ... bu qism o'zgarishsiz qoladi ...
        operation_description="Tanlangan arizaga yangi hujjat (fayl) yuklash.",
        manual_parameters=[
            openapi.Parameter(name="file", in_=openapi.IN_FORM, type=openapi.TYPE_FILE, required=True, description="Tizimga yuklanadigan hujjat"),
            openapi.Parameter(name="description", in_=openapi.IN_FORM, type=openapi.TYPE_STRING, required=False, description="Hujjat uchun qisqa izoh"),
        ],
        request_body=None,
        responses={ 201: DocumentSerializer, 404: "Ariza topilmadi" }
    )
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    # --- 🔄 MANA SHU METODNI YANGILANG 🔄 ---
    def perform_create(self, serializer):
        application_id = self.kwargs.get("application_id")
        user = self.request.user

        # So'rov uchun parametrlarni tayyorlaymiz
        query_params = {'id': application_id}

        # Agar so'rov yuborayotgan foydalanuvchi oddiy 'user' (bemor) bo'lsa,
        # uning faqat o'ziga tegishli arizani tekshiramiz.
        if getattr(user, 'role', None) == 'user':
            query_params['patient'] = user

        # Agar foydalanuvchi 'operator' yoki 'admin' bo'lsa, 'patient' bo'yicha filtr qo'llanilmaydi.
        # Shu sababli ular istalgan arizani topa oladi.
        application = get_object_or_404(Application, **query_params)

        serializer.save(application=application)

class DocumentListCreateView(generics.ListCreateAPIView):
    """
    Muayyan arizaga tegishli hujjatlarni olish (GET) va yangi hujjat yuklash (POST).
    """
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser] # POST uchun kerak

    def get_queryset(self):
        # Ro'yxatni olish uchun mantiq (DocumentListView'dan)
        application_id = self.kwargs.get("application_id")

        # Xavfsizlik: Bemor faqat o'zining arizasidagi hujjatlarni ko'rsin
        if getattr(self.request.user, 'role', 'user') == 'user':
            application = get_object_or_404(Application, id=application_id, patient=self.request.user)
        else: # Operator/Admin istalganini ko'ra oladi
            application = get_object_or_404(Application, id=application_id)

        return Document.objects.filter(application=application)

    @swagger_auto_schema(
        # Fayl yuklash uchun Swagger sozlamalari (DocumentCreateView'dan)
        operation_description="Tanlangan arizaga yangi hujjat (fayl) yuklash.",
        manual_parameters=[
            openapi.Parameter(name="file", in_=openapi.IN_FORM, type=openapi.TYPE_FILE, required=True, description="Tizimga yuklanadigan hujjat"),
            openapi.Parameter(name="description", in_=openapi.IN_FORM, type=openapi.TYPE_STRING, required=False, description="Hujjat uchun qisqa izoh"),
        ],
        request_body=None
    )
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def perform_create(self, serializer):
        # Hujjat yaratish uchun mantiq (DocumentCreateView'dan)
        application_id = self.kwargs.get("application_id")
        user = self.request.user
        query_params = {'id': application_id}
        if getattr(user, 'role', None) == 'user':
            query_params['patient'] = user

        application = get_object_or_404(Application, **query_params)
        serializer.save(application=application)
class DocumentListView(generics.ListAPIView):
    """Hujjatlarni olish"""
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Document.objects.none()
        user = self.request.user
        if not user.is_authenticated:
            return Document.objects.none()
        if user.role == "user":
            return Document.objects.filter(application__patient=user)
        elif user.role in ["doctor", "admin", "operator"]:
            return Document.objects.all()
        return Document.objects.none()

class ChangeApplicationStageView(APIView):
    permission_classes = [permissions.IsAuthenticated]  # yoki custom IsAdminOrOperator

    @swagger_auto_schema(
        operation_description="Arizaning bosqichini (stage) o‘zgartirish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["new_stage_id"],
            properties={
                "new_stage_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Yangi Stage ID"),
                "comment": openapi.Schema(type=openapi.TYPE_STRING, description="Izoh (majburiy emas)"),
            },
        ),
        responses={200: openapi.Response("Stage muvaffaqiyatli o‘zgartirildi")}
    )
    def patch(self, request, application_id):
        user = request.user

        # Operator yoki Admin ekanligini tekshirish
        if getattr(user, 'role', 'user') not in ['admin', 'operator']:
            raise PermissionDenied("Sizda bosqichni o'zgartirishga ruxsat yo'q.")

        # Arizani topamiz
        application = get_object_or_404(Application, id=application_id)

        new_stage_id = request.data.get("new_stage_id")
        if not new_stage_id:
            return Response(
                {"error": "'new_stage_id' majburiy."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_stage = get_object_or_404(Stage, id=new_stage_id)
        old_stage = application.stage

        # Bosqichni o‘zgartiramiz
        application.stage = new_stage
        application.save(update_fields=["stage"])

        comment = request.data.get(
            "comment",
            f"Bosqich o‘zgartirildi: {getattr(old_stage, 'name', '—')} → {new_stage.name}",
        )

        # ApplicationHistory ga yozib qo‘yamiz
        ApplicationHistory.objects.create(application=application, author=user, comment=comment)

        return Response(
            {"success": True, "new_stage": new_stage.name},
            status=status.HTTP_200_OK,
        )