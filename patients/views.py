from datetime import timedelta

from django.utils import timezone
from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Patient, PatientHistory, PatientDocument, ChatMessage, Contract
from .serializers import (
    PatientListSerializer,
    PatientDetailSerializer,
    PatientCreateUpdateSerializer,
    PatientProfileSerializer,
    PatientDocumentSerializer,
    PatientHistorySerializer,
    ChatMessageSerializer,
)
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Patient, PatientHistory
from .serializers import (
    PatientListSerializer,
    PatientDetailSerializer,
    PatientCreateUpdateSerializer,
    PatientProfileSerializer,
    PatientHistorySerializer,
)
from core.models import Stage, Tag


# ===============================================================
# 🧩 YORDAMCHI FUNKSIYA - Tarix yozish
# ===============================================================
def log_patient_history(patient, user, comment):
    """
    Bemorga tarix yozish uchun universal yordamchi funksiya.
    Har qanday xatoni tutadi, xavfsiz ishlaydi.
    """
    try:
        if not patient or not user:
            print("[HISTORY WARNING] Patient yoki User yo'q")
            return
        PatientHistory.objects.create(
            patient=patient,
            author=user,
            comment=comment
        )
        print(f"[PATIENT LOG] {comment}")
    except Exception as e:
        print(f"[PATIENT HISTORY ERROR] Tarix yozishda xato: {str(e)}")


# ===============================================================
# 📄 PAGINATION
# ===============================================================
class PatientPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ===============================================================
# 👤 PATIENT VIEWSET
# ===============================================================
class PatientViewSet(viewsets.ModelViewSet):
    """
    👤 Bemorlar API
    - List: Barcha bemorlar (Kanban board uchun minimal ma'lumotlar)
    - Retrieve: Bitta bemor (to'liq ma'lumotlar - applications, documents, history)
    - Create: Yangi bemor yaratish
    - Update: Bemor ma'lumotlarini yangilash
    - Delete: Bemorni o'chirish
    """
    queryset = Patient.objects.all().select_related('stage', 'tag').order_by('-id')
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = PatientPagination

    def get_serializer_class(self):
        """Har xil action uchun mos serializer"""
        if self.action == 'retrieve':
            return PatientDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return PatientCreateUpdateSerializer
        elif self.action == 'profile':
            return PatientProfileSerializer
        return PatientListSerializer

    def get_serializer_context(self):
        """Context - file URL'lar uchun request kerak"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        """Queryset - filter va search bilan"""
        queryset = Patient.objects.all().select_related('stage', 'tag')

        # 🆔 Patient ID bo'yicha filter (bitta bemor)
        patient_id = self.request.query_params.get('patient_id')
        if patient_id:
            queryset = queryset.filter(id=patient_id)

        # 🔍 Qidiruv (ism, telefon, email)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(phone_number__icontains=search) |
                Q(email__icontains=search)
            )

        # 🏷️ Stage bo'yicha filter (Kanban columns uchun)
        stage_id = self.request.query_params.get('stage_id')
        if stage_id:
            queryset = queryset.filter(stage_id=stage_id)

        # 🏷️ Tag bo'yicha filter
        tag_id = self.request.query_params.get('tag_id')
        if tag_id:
            queryset = queryset.filter(tag_id=tag_id)

        # 📅 Sana bo'yicha filter
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset.order_by('-created_at')

    # ===========================================================
    # 📋 LIST
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="👤 Barcha bemorlar ro'yxati (Kanban board uchun)",
        operation_description="Bemorlar ro'yxati - minimal ma'lumotlar (id, ism, telefon, stage_id, tag_id). Kanban board uchun optimizatsiya qilingan.",
        manual_parameters=[
            openapi.Parameter('patient_id', openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Bitta bemor bo'yicha filter (patient ID)"),
            openapi.Parameter('search', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Ism, telefon yoki email bo'yicha qidirish"),
            openapi.Parameter('stage_id', openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Stage bo'yicha filter (Kanban column)"),
            openapi.Parameter('tag_id', openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Tag bo'yicha filter"),
            openapi.Parameter('date_from', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Yaratilgan sana (dan) - format: YYYY-MM-DD"),
            openapi.Parameter('date_to', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="Yaratilgan sana (gacha) - format: YYYY-MM-DD"),
            openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Sahifa raqami"),
            openapi.Parameter('page_size', openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description="Sahifadagi elementlar soni (max 100)"),
        ],
        responses={200: PatientListSerializer(many=True)},
        tags=["patients"]
    )
    def list(self, request, *args, **kwargs):
        """Bemorlar ro'yxati - Kanban board uchun"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ===========================================================
    # 🔍 RETRIEVE
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="👤 Bemor to'liq ma'lumotlari",
        operation_description="Bemorning barcha ma'lumotlari: shaxsiy ma'lumotlar, arizalar (applications), hujjatlar (documents), tarix (history)",
        responses={200: PatientDetailSerializer()},
        tags=["patients"]
    )
    def retrieve(self, request, *args, **kwargs):
        patient = self.get_object()
        serializer = self.get_serializer(patient)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ===========================================================
    # ➕ CREATE
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="👤 Yangi bemor yaratish",
        operation_description="Yangi bemor qo'shish. Avatar yuklash mumkin.",
        request_body=PatientCreateUpdateSerializer,
        responses={201: PatientCreateUpdateSerializer()},
        tags=["patients"]
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = serializer.save()
        log_patient_history(patient, request.user, f"📝 Bemor ro'yxatga olindi: {patient.full_name}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # ===========================================================
    # 🔄 UPDATE
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="👤 Bemor ma'lumotlarini yangilash (PUT)",
        operation_description="Bemorning barcha ma'lumotlarini yangilash",
        request_body=PatientCreateUpdateSerializer,
        responses={200: PatientCreateUpdateSerializer()},
        tags=["patients"]
    )
    def update(self, request, *args, **kwargs):
        patient = self.get_object()
        serializer = self.get_serializer(patient, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_patient_history(patient, request.user, "🔄 Bemor ma'lumotlari yangilandi")
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ===========================================================
    # ✏️ PARTIAL UPDATE
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="👤 Bemor ma'lumotlarini qisman yangilash (PATCH)",
        operation_description="Bemorning ayrim maydonlarini o'zgartirish",
        request_body=PatientCreateUpdateSerializer,
        responses={200: PatientCreateUpdateSerializer()},
        tags=["patients"]
    )
    def partial_update(self, request, *args, **kwargs):
        patient = self.get_object()
        serializer = self.get_serializer(patient, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_patient_history(patient, request.user, "✏️ Bemor ma'lumotlari qisman yangilandi")
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ===========================================================
    # 🗑️ DESTROY
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="👤 Bemorni o'chirish",
        operation_description="Bemorni tizimdan o'chirish",
        responses={204: "Bemor muvaffaqiyatli o'chirildi"},
        tags=["patients"]
    )
    def destroy(self, request, *args, **kwargs):
        patient = self.get_object()
        patient_name = patient.full_name
        log_patient_history(patient, request.user, f"🗑️ Bemor o'chirildi: {patient_name}")
        patient.delete()
        return Response(
            {"detail": f"Bemor '{patient_name}' muvaffaqiyatli o'chirildi"},
            status=status.HTTP_204_NO_CONTENT
        )

    # ===========================================================
    # 🕓 HISTORY LIST / ADD
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="🕓 Bemor tarixi",
        operation_description="Bemorning barcha o'zgarishlar tarixi",
        responses={200: PatientHistorySerializer(many=True)},
        tags=["patients"]
    )
    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        patient = self.get_object()
        history = PatientHistory.objects.filter(patient=patient).select_related('author').order_by('-created_at')
        serializer = PatientHistorySerializer(history, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="🕓 Bemorga izoh qo'shish",
        operation_description="Bemor tarixiga yangi izoh yozish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['comment'],
            properties={'comment': openapi.Schema(type=openapi.TYPE_STRING)},
        ),
        responses={201: PatientHistorySerializer()},
        tags=["patients"]
    )
    @action(detail=True, methods=['post'], url_path='history/add')
    def add_history(self, request, pk=None):
        patient = self.get_object()
        comment = request.data.get('comment')
        if not comment:
            return Response({"detail": "Izoh matni kiritilmagan"}, status=400)
        log_patient_history(patient, request.user, comment)
        return Response({"success": True}, status=201)

    # ===========================================================
    # 🏷️ STAGE / TAG CHANGE
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="🏷️ Bemorning stage'ini o'zgartirish",
        operation_description="Bemorni boshqa stage'ga ko'chirish (Kanban board uchun)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['stage_id'],
            properties={
                'stage_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'comment': openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: openapi.Response("Stage muvaffaqiyatli o'zgartirildi")},
        tags=["patients"]
    )
    @action(detail=True, methods=['patch'], url_path='change-stage')
    def change_stage(self, request, pk=None):
        patient = self.get_object()
        stage_id = request.data.get('stage_id')
        comment = request.data.get('comment', '')
        if not stage_id:
            return Response({"detail": "stage_id kiritilmagan"}, status=400)
        try:
            new_stage = Stage.objects.get(id=stage_id)
        except Stage.DoesNotExist:
            return Response({"detail": "Stage topilmadi"}, status=404)
        old_stage = patient.stage.title if patient.stage else "Yo'q"
        patient.stage = new_stage
        patient.save(update_fields=['stage'])
        history_comment = comment or f"Stage '{old_stage}' → '{new_stage.title}' ga o'zgartirildi"
        log_patient_history(patient, request.user, history_comment)
        return Response({"success": True, "new_stage": new_stage.title}, status=200)

    @swagger_auto_schema(
        operation_summary="🏷️ Bemorning tag'ini o'zgartirish",
        operation_description="Bemorga tag qo'shish yoki o'zgartirish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={'tag_id': openapi.Schema(type=openapi.TYPE_INTEGER)},
        ),
        responses={200: openapi.Response("Tag muvaffaqiyatli o'zgartirildi")},
        tags=["patients"]
    )
    @action(detail=True, methods=['patch'], url_path='change-tag')
    def change_tag(self, request, pk=None):
        patient = self.get_object()
        tag_id = request.data.get('tag_id')
        if tag_id:
            try:
                new_tag = Tag.objects.get(id=tag_id)
                patient.tag = new_tag
                patient.save(update_fields=['tag'])
                log_patient_history(patient, request.user, f"Tag '{new_tag.name}' qo'shildi")
                return Response({"success": True, "new_tag": new_tag.name}, status=200)
            except Tag.DoesNotExist:
                return Response({"detail": "Tag topilmadi"}, status=404)
        else:
            patient.tag = None
            patient.save(update_fields=['tag'])
            log_patient_history(patient, request.user, "Tag o'chirildi")
            return Response({"success": True, "new_tag": None}, status=200)

    # ===========================================================
    # 👤 PROFILE
    # ===========================================================
    @swagger_auto_schema(
        operation_summary="👤 Bemor profili",
        operation_description="Bemorning profil ma'lumotlari (frontend profil sozlamalari uchun)",
        responses={200: PatientProfileSerializer()},
        tags=["patients"]
    )
    @action(detail=True, methods=['get'], url_path='profile')
    def profile(self, request, pk=None):
        patient = self.get_object()
        serializer = PatientProfileSerializer(patient, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

# ===============================================================
# 📎 PATIENT DOCUMENT VIEWSET
# ===============================================================
class PatientDocumentViewSet(viewsets.ModelViewSet):
    """
    📎 Bemor hujjatlari API
    - List: Bemorning barcha hujjatlari
    - Create: Yangi hujjat yuklash
    - Retrieve: Bitta hujjat
    - Delete: Hujjatni o'chirish
    """
    serializer_class = PatientDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        """Patient ID bo'yicha filter"""
        patient_id = self.kwargs.get('patient_pk')
        if patient_id:
            return PatientDocument.objects.filter(patient_id=patient_id).order_by('-uploaded_at')
        return PatientDocument.objects.all().order_by('-uploaded_at')

    def get_serializer_context(self):
        """Context qo'shish"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @swagger_auto_schema(
        operation_summary="📎 Bemor hujjatlari ro'yxati",
        operation_description="Bemorning barcha yuklangan hujjatlari",
        responses={200: PatientDocumentSerializer(many=True)},
        tags=["patient-documents"]
    )
    def list(self, request, patient_pk=None):
        """Bemor hujjatlari ro'yxati"""
        documents = self.get_queryset()
        serializer = self.get_serializer(documents, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="📎 Hujjat yuklash",
        operation_description="Bemor uchun yangi hujjat yuklash (PDF, JPG, PNG, DOCX)",
        request_body=PatientDocumentSerializer,
        responses={201: PatientDocumentSerializer()},
        tags=["patient-documents"]
    )
    def create(self, request, patient_pk=None):
        """Yangi hujjat yuklash"""
        patient = get_object_or_404(Patient, pk=patient_pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save(patient=patient, uploaded_by=request.user)

        # History yozish
        PatientHistory.objects.create(
            patient=patient,
            author=request.user,
            comment=f"📎 Hujjat yuklandi: {document.file.name if document.file else 'Unknown'}"
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_summary="📎 Hujjatni o'chirish",
        operation_description="Bemorning hujjatini o'chirish",
        responses={204: "Hujjat muvaffaqiyatli o'chirildi"},
        tags=["patient-documents"]
    )
    def destroy(self, request, patient_pk=None, pk=None):
        """Hujjatni o'chirish"""
        document = self.get_object()
        patient = document.patient
        file_name = document.file.name if document.file else 'Unknown'
        document.delete()

        # History yozish
        PatientHistory.objects.create(
            patient=patient,
            author=request.user,
            comment=f"🗑️ Hujjat o'chirildi: {file_name}"
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


# ===============================================================
# 📧 RESPONSE LETTERS VIEWSET
# ===============================================================
class ResponseLettersViewSet(viewsets.ReadOnlyModelViewSet):
    """
    📧 Javob xatlari (Response Letters)
    - Bemorga yuborilgan rasmiy xatlar
    - Faqat o'qish uchun
    """
    serializer_class = PatientDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Faqat response letter hujjatlar"""
        patient_id = self.kwargs.get('patient_pk')
        if patient_id:
            # Agar description'da "response" yoki "letter" so'zi bo'lsa
            return PatientDocument.objects.filter(
                patient_id=patient_id,
                description__icontains='response'
            ).order_by('-uploaded_at')
        return PatientDocument.objects.filter(
            description__icontains='response'
        ).order_by('-uploaded_at')

    def get_serializer_context(self):
        """Context qo'shish"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @swagger_auto_schema(
        operation_summary="📧 Javob xatlari ro'yxati",
        operation_description="Bemorga yuborilgan barcha javob xatlari",
        responses={200: PatientDocumentSerializer(many=True)},
        tags=["response-letters"]
    )
    def list(self, request, patient_pk=None):
        """Javob xatlari ro'yxati"""
        letters = self.get_queryset()
        serializer = self.get_serializer(letters, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ===============================================================
# 📝 CONTRACT APPROVE VIEWSET
# ===============================================================
class ContractApproveViewSet(viewsets.ViewSet):
    """
    📝 Shartnoma tasdiqlash
    - Bemorning shartnomalarini ko'rish va tasdiqlash
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="📝 Bemor shartnomalarini olish",
        operation_description="Bemorning barcha shartnomalarini ko'rish",
        responses={200: openapi.Response("Shartnomalar ro'yxati")},
        tags=["contracts"]
    )
    def list(self, request, patient_pk=None):
        """Bemor shartnomalarini olish"""
        try:
            contracts = Contract.objects.filter(patient_id=patient_pk).order_by('-created_at')
            data = []
            for contract in contracts:
                data.append({
                    'id': contract.id,
                    'patient_id': contract.patient.id if contract.patient else None,
                    'title': getattr(contract, 'title', 'Shartnoma'),
                    'content': getattr(contract, 'content', ''),
                    'is_approved': getattr(contract, 'is_approved', False),
                    'approved_at': getattr(contract, 'approved_at', None),
                    'created_at': contract.created_at if hasattr(contract, 'created_at') else None,
                })
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"detail": f"Xatolik: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        operation_summary="📝 Shartnomani tasdiqlash",
        operation_description="Bemor shartnomani tasdiqlaydi",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'is_approved': openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Tasdiqlash (true/false)"),
            }
        ),
        responses={200: openapi.Response("Shartnoma tasdiqlandi")},
        tags=["contracts"]
    )
    @action(detail=True, methods=['patch'], url_path='approve')
    def approve(self, request, patient_pk=None, pk=None):
        """Shartnomani tasdiqlash"""
        try:
            contract = get_object_or_404(Contract, pk=pk, patient_id=patient_pk)
            is_approved = request.data.get('is_approved', True)

            if hasattr(contract, 'is_approved'):
                contract.is_approved = is_approved
            if hasattr(contract, 'approved_at') and is_approved:
                from django.utils import timezone
                contract.approved_at = timezone.now()

            contract.save()

            # History yozish
            patient = contract.patient
            PatientHistory.objects.create(
                patient=patient,
                author=request.user,
                comment=f"✅ Shartnoma {'tasdiqlandi' if is_approved else 'rad etildi'}"
            )

            return Response({
                "success": True,
                "message": f"Shartnoma {'tasdiqlandi' if is_approved else 'rad etildi'}"
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"detail": f"Xatolik: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


# ===============================================================
# 👤 ME PROFILE VIEW (Joriy foydalanuvchi)
# ===============================================================
# patients/views.py
# ===============================================================
# ME PROFILE VIEW - JWT TOKEN ORQALI USER PROFILI
# ===============================================================
class MeProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        user = self.request.user

        # 1. Phone number orqali (asosiy usul)
        if hasattr(user, 'phone_number') and user.phone_number:
            try:
                return Patient.objects.select_related('stage', 'tag').get(
                    phone_number=user.phone_number
                )
            except Patient.DoesNotExist:
                pass

        # 2. User ID orqali (created_by)
        try:
            return Patient.objects.select_related('stage', 'tag').get(
                created_by=user
            )
        except Patient.DoesNotExist:
            pass

        # 3. Profil topilmadi
        return None

    def get_serializer_context(self):
        """Context - file URL'lar uchun request kerak"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @swagger_auto_schema(
        operation_summary=" Mening profilim",
        responses={
            200: PatientProfileSerializer(),
            401: "Autentifikatsiya xatosi (JWT token yo'q yoki yaroqsiz)",
            404: "Profil topilmadi"
        },
        tags=["me-profile"]
    )
    def get(self, request, *args, **kwargs):
        """Profil ma'lumotlarini olish"""
        patient = self.get_object()

        if not patient:
            return Response(
                {
                    "detail": "Profil topilmadi",
                    "help": "Iltimos, avval profil yarating (PUT yoki PATCH so'rovini yuboring)"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(patient)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Profilni qisman yangilash",
        operation_description="""
        Profil ma'lumotlarini qisman yangilash (PATCH).

        Agar profil yo'q bo'lsa - yangi profil yaratadi.

        Faqat yuborilgan fieldlar yangilanadi.
        """,
        request_body=PatientProfileSerializer,
        responses={
            200: PatientProfileSerializer(),
            201: "Yangi profil yaratildi",
            400: "Validation xatosi",
            401: "JWT token xatosi"
        },
        tags=["me-profile"]
    )
    def patch(self, request, *args, **kwargs):
        patient = self.get_object()

        if not patient:
            return self.create_profile(request)
        serializer = self.get_serializer(patient, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # created_by ni saqlash
        if not patient.created_by:
            patient.created_by = request.user

        serializer.save()

        # History
        try:
            PatientHistory.objects.create(
                patient=patient,
                author=request.user,
                comment="Profil ma'lumotlari yangilandi (PATCH)"
            )
        except:
            pass

        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Profilni to'liq yangilash",
        request_body=PatientProfileSerializer,
        responses={
            200: PatientProfileSerializer(),
            201: "Yangi profil yaratildi",
            400: "Validation xatosi",
            401: "JWT token xatosi"
        },
        tags=["me-profile"]
    )
    def put(self, request, *args, **kwargs):
        """Profilni to'liq yangilash"""
        patient = self.get_object()

        if not patient:
            # Profil yo'q - yangi yaratish
            return self.create_profile(request)

        # Mavjud profilni yangilash
        serializer = self.get_serializer(patient, data=request.data)
        serializer.is_valid(raise_exception=True)

        # created_by ni saqlash
        if not patient.created_by:
            patient.created_by = request.user

        serializer.save()

        # History
        try:
            PatientHistory.objects.create(
                patient=patient,
                author=request.user,
                comment="Profil ma'lumotlari yangilandi (PUT)"
            )
        except:
            pass

        return Response(serializer.data, status=status.HTTP_200_OK)

    def create_profile(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = serializer.save(created_by=request.user)
        if not patient.phone_number and hasattr(request.user, 'phone_number'):
            patient.phone_number = request.user.phone_number
            patient.save()

        # History
        try:
            PatientHistory.objects.create(
                patient=patient,
                author=request.user,
                comment="Yangi profil yaratildi"
            )
        except:
            pass

        return Response(serializer.data, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method='get',
    operation_summary="📊 Bemorlar statistikasi",
    operation_description="""
    ✅ Operator uchun statistika:
    - Jami bemorlar
    - Yangi bemorlar (oxirgi 7 kun)
    - Faol bemorlar (arizalari bor)
    - Erkak bemorlar
    - Ayol bemorlar
    """,
    responses={
        200: openapi.Response(
            'Success',
            openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'jami_bemorlar': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'yangi_bemorlar': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'faol_bemorlar': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'erkak': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'ayol': openapi.Schema(type=openapi.TYPE_INTEGER),
                }
            )
        )
    },
    tags=["statistics"]
)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def patient_statistics(request):
    """
    ✅ TO'G'RILANGAN - Bemorlar statistikasi

    GET /api/patients/statistics/
    """
    try:
        # ✅ 1. Jami bemorlar
        jami_bemorlar = Patient.objects.count()

        # ✅ 2. Yangi bemorlar (oxirgi 7 kun)
        seven_days_ago = timezone.now() - timedelta(days=7)
        yangi_bemorlar = Patient.objects.filter(
            created_at__gte=seven_days_ago
        ).count()

        # ✅ 3. Faol bemorlar (arizalari bor) - TO'G'RILANDI
        try:
            from applications.models import Application

            # TO'G'RI usul - subquery
            faol_bemorlar = Patient.objects.filter(
                id__in=Application.objects.values_list('patient_id', flat=True).distinct()
            ).count()

        except Exception as app_error:
            print(f"Application model xatosi: {app_error}")
            faol_bemorlar = 0

        # ✅ 4. Jins bo'yicha statistika
        erkak = Patient.objects.filter(gender='male').count()
        ayol = Patient.objects.filter(gender='female').count()

        return Response({
            'jami_bemorlar': jami_bemorlar,
            'yangi_bemorlar': yangi_bemorlar,
            'faol_bemorlar': faol_bemorlar,
            'erkak': erkak,
            'ayol': ayol,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        print(f"Statistics xatosi: {str(e)}")
        print(traceback.format_exc())

        return Response(
            {'detail': f'Xato: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
