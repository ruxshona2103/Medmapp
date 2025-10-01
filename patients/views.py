from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.utils import timezone
import logging
from django.shortcuts import get_object_or_404
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, NotFound
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Patient, PatientProfile, Stage, Tag, PatientHistory, PatientDocument
from .serializers import (
    PatientSerializer,
    PatientProfileSerializer,
    StageSerializer,
    TagSerializer,
    PatientDocumentSerializer,
    UserSerializer,
    ApplicationStepSerializer,
)
from applications.models import Application
from applications.serializers import ApplicationSerializer

User = get_user_model()
logger = logging.getLogger(__name__)


def _is_swagger(view) -> bool:
    return getattr(view, "swagger_fake_view", False)


def _norm_role(user):
    if not hasattr(user, "role"):
        return "anonymous"
    role = getattr(user, "role", "").lower()
    return "patient" if role == "user" else role


class PatientProfileListView(generics.ListAPIView):
    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        if _is_swagger(self) or not self.request.user.is_authenticated:
            return PatientProfile.objects.none()

        user = self.request.user
        role = _norm_role(user)
        base = PatientProfile.objects.select_related("user").prefetch_related(
            "patient_records__documents", "patient_records__history"
        )
        if role == "patient":
            # Ensure PatientProfile exists for the user
            profile, created = PatientProfile.objects.get_or_create(
                user=user,
                defaults={
                    "full_name": user.get_full_name() or user.phone_number or "Noma'lum",
                    "gender": "male",
                    "complaints": "",
                    "previous_diagnosis": "",
                },
            )
            if created:
                logger.info(f"Created PatientProfile for User {user.id} in PatientProfileListView")
            return base.filter(user=user)
        return base


class PatientListView(generics.ListAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["patient", "status"]

    def get_queryset(self):
        if _is_swagger(self) or not self.request.user.is_authenticated:
            logger.info("Swagger or unauthenticated user, returning empty queryset")
            return Application.objects.none()

        user = self.request.user
        role = _norm_role(user)
        logger.info(f"User: {user.phone_number}, Role: {role}")

        self.create_missing_profiles_for_applications()

        queryset = Application.objects.select_related("patient").all()

        if role == "patient":
            queryset = queryset.filter(patient=user)
            logger.info(f"Patient applications count: {queryset.count()}")
            return queryset

        if role in ["superadmin", "operator"]:
            return queryset

        one_day_ago = timezone.now() - timezone.timedelta(days=1)
        queryset = queryset.filter(created_at__lte=one_day_ago)
        logger.info(f"Filtered applications count (older than 1 day): {queryset.count()}")
        return queryset

    def create_missing_profiles_for_applications(self):
        applications = Application.objects.select_related("patient").all()
        created_count = 0

        for app in applications:
            user = app.patient
            logger.info(
                f"Processing Application {app.id} for User {user.id} ({user.phone_number})"
            )

            profile, profile_created = PatientProfile.objects.get_or_create(
                user=user,
                defaults={
                    "full_name": user.get_full_name() or user.phone_number or "Noma'lum",
                    "gender": "male",
                    "complaints": app.complaint or "",
                    "previous_diagnosis": app.diagnosis or "",
                },
            )
            if profile_created:
                logger.info(f"Created PatientProfile: {profile.id} for Application {app.id}")
                created_count += 1

            patient, patient_created = Patient.objects.get_or_create(
                profile=profile,
                source=f"Application_{app.id}",
                defaults={
                    "full_name": profile.full_name or user.get_full_name() or "Noma'lum",
                    "phone": user.phone_number,
                    "email": getattr(user, "email", None),
                    "created_by": user,
                    "created_at": timezone.now(),
                    "stage": Stage.objects.filter(code_name=app.status).first(),
                },
            )
            if patient_created:
                logger.info(f"Created Patient: {patient.id} for Application {app.id}")
            else:
                patient.full_name = profile.full_name or user.get_full_name() or "Noma'lum"
                patient.stage = Stage.objects.filter(code_name=app.status).first()
                patient.save(update_fields=["full_name", "stage"])
                logger.info(f"Updated Patient: {patient.id} for Application {app.id}")

        if created_count > 0:
            logger.info(f"Created {created_count} PatientProfile(s) for Applications")
        else:
            logger.info("No new PatientProfiles created, all exist or updated")


class ApplicationCreateView(generics.CreateAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        role = _norm_role(user)
        patient_data = serializer.validated_data.pop("patient_data")

        if role == "patient":
            patient_user = user
            if patient_data.get("first_name"):
                patient_user.first_name = patient_data.get("first_name")
            if patient_data.get("last_name"):
                patient_user.last_name = patient_data.get("last_name")
            if patient_data.get("email"):
                patient_user.email = patient_data.get("email")
            patient_user.save(update_fields=["first_name", "last_name", "email"])
        else:
            phone_number = patient_data.get("phone_number")
            patient_user, created = User.objects.get_or_create(
                phone_number=phone_number,
                defaults={
                    "username": phone_number,
                    "first_name": patient_data.get("first_name", ""),
                    "last_name": patient_data.get("last_name", ""),
                    "email": patient_data.get("email", None),
                    "role": "user",
                },
            )
            if created:
                logger.info(f"Created new User: {patient_user.phone_number}")
            else:
                if patient_data.get("first_name"):
                    patient_user.first_name = patient_data.get("first_name")
                if patient_data.get("last_name"):
                    patient_user.last_name = patient_data.get("last_name")
                if patient_data.get("email"):
                    patient_user.email = patient_data.get("email")
                patient_user.save(update_fields=["first_name", "last_name", "email"])

        application = serializer.save(patient=patient_user)

        profile, profile_created = PatientProfile.objects.get_or_create(
            user=patient_user,
            defaults={
                "full_name": patient_user.get_full_name() or patient_user.phone_number or "Noma'lum",
                "gender": "male",
                "complaints": application.complaint or "",
                "previous_diagnosis": application.diagnosis or "",
            },
        )
        if profile_created:
            logger.info(f"Created PatientProfile: {profile.id} for Application {application.id}")

        patient, patient_created = Patient.objects.get_or_create(
            profile=profile,
            source=f"Application_{application.id}",
            defaults={
                "full_name": profile.full_name or patient_user.get_full_name() or "Noma'lum",
                "phone": patient_user.phone_number,
                "email": getattr(patient_user, "email", None),
                "created_by": user,
                "created_at": timezone.now(),
                "stage": Stage.objects.filter(code_name=application.status).first(),
            },
        )
        if patient_created:
            logger.info(f"Created Patient: {patient.id} for Application {application.id}")
        else:
            patient.full_name = profile.full_name or patient_user.get_full_name() or "Noma'lum"
            patient.stage = Stage.objects.filter(code_name=application.status).first()
            patient.save(update_fields=["full_name", "stage"])
            logger.info(f"Updated Patient: {patient.id} for Application {application.id}")

        logger.info(f"Created Application: {application.application_id} for {patient_user.phone_number}")


class PatientMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Retrieve or update the authenticated patient's profile.",
        responses={
            200: PatientProfileSerializer,
            403: 'Permission Denied - Only patients can access this endpoint',
        },
    )
    def get(self, request):
        if _is_swagger(self):
            return Response({})

        user = self.request.user
        if _norm_role(user) != "patient":
            raise PermissionDenied("Faqat bemorlar uchun.")

        profile, created = PatientProfile.objects.get_or_create(
            user=user,
            defaults={
                "full_name": user.get_full_name() or user.phone_number or "Noma'lum",
                "gender": "male",
                "complaints": "",
                "previous_diagnosis": "",
            },
        )
        if created:
            logger.info(f"Created PatientProfile for User {user.id} in PatientMeView")

        serializer = PatientProfileSerializer(profile, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        request_body=PatientProfileSerializer,
        responses={
            200: PatientProfileSerializer,
            403: 'Permission Denied - Only patients can access this endpoint',
        },
    )
    def patch(self, request):
        if _is_swagger(self):
            return Response({})

        user = self.request.user
        if _norm_role(user) != "patient":
            raise PermissionDenied("Faqat bemorlar uchun.")

        profile, created = PatientProfile.objects.get_or_create(
            user=user,
            defaults={
                "full_name": user.get_full_name() or user.phone_number or "Noma'lum",
                "gender": "male",
                "complaints": "",
                "previous_diagnosis": "",
            },
        )
        if created:
            logger.info(f"Created PatientProfile for User {user.id} in PatientMeView")

        serializer = PatientProfileSerializer(
            profile, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated_instance = serializer.save()

        if hasattr(updated_instance, "patient_records"):
            for patient in updated_instance.patient_records.all():
                if "full_name" in request.data:
                    patient.full_name = request.data.get("full_name", patient.full_name)
                if "email" in request.data:
                    patient.email = request.data.get("email", patient.email)
                if "region" in request.data:
                    patient.region = request.data.get("region", patient.region)
                patient.save(update_fields=["full_name", "email", "region"])

        return Response(serializer.data)


class PatientCreateView(generics.CreateAPIView):
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        role = _norm_role(user)
        patient = serializer.save(created_by=user)

        if role == "patient":
            profile, created = PatientProfile.objects.get_or_create(
                user=user,
                defaults={
                    "full_name": user.get_full_name() or user.phone_number or "Noma'lum",
                    "gender": "male",
                    "complaints": "",
                    "previous_diagnosis": "",
                },
            )
            if created:
                logger.info(f"Created PatientProfile for User {user.id} in PatientCreateView")
            patient.profile = profile
            patient.full_name = user.get_full_name() or user.phone_number
            patient.phone = user.phone_number
            patient.email = self.request.data.get("email")
            patient.save()
        else:
            if not patient.profile:
                raise NotFound("Bemor profili mavjud emas.")

        PatientHistory.objects.create(
            patient=patient, author=user, comment="Bemor jarayoni tizimga qo'shildi"
        )
        logger.info(f"Created Patient: {patient.full_name}")


class OperatorMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if _is_swagger(self):
            return Response({})
        user = self.request.user
        if _norm_role(user) != "operator":
            raise PermissionDenied("Faqat operatorlar uchun.")
        return Response(UserSerializer(user, context={"request": request}).data)


class ChangeStageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, patient_id):
        if _is_swagger(self):
            return Response({})

        patient = get_object_or_404(Patient, id=patient_id)
        user = request.user

        if _norm_role(user) == "patient":
            raise PermissionDenied("Bemorlar bosqichni o‘zgartira olmaydi.")

        new_stage_id = request.data.get("new_stage_id")
        if not new_stage_id:
            return Response(
                {"error": "'new_stage_id' majburiy."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_stage = get_object_or_404(Stage, id=new_stage_id)
        old_stage = patient.stage
        patient.stage = new_stage
        patient.save(update_fields=["stage"])

        comment = request.data.get(
            "comment",
            f"Bosqich o‘zgartirildi: {getattr(old_stage, 'title', '—')} → {new_stage.title}",
        )
        PatientHistory.objects.create(patient=patient, author=user, comment=comment)

        return Response(
            {"success": True, "new_stage": new_stage.title}, status=status.HTTP_200_OK
        )


class PatientDocumentCreateView(generics.CreateAPIView):
    serializer_class = PatientDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        patient_id = self.kwargs.get("patient_id")
        patient = get_object_or_404(Patient, id=patient_id)
        user = self.request.user
        role = _norm_role(user)

        if role == "patient" and patient.profile.user != user:
            raise PermissionDenied("Siz faqat o‘zingiz uchun hujjat yuklay olasiz.")

        source_type = role if role in ["operator", "patient", "partner"] else "operator"
        serializer.save(patient=patient, uploaded_by=user, source_type=source_type)


class PatientDocumentDeleteView(generics.DestroyAPIView):
    serializer_class = PatientDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if _is_swagger(self):
            return PatientDocument.objects.none()
        return PatientDocument.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user
        role = _norm_role(user)

        if role == "patient" and instance.patient.profile.user != user:
            raise PermissionDenied("Siz faqat o‘zingiz yuklagan hujjatlarni o‘chira olasiz.")
        if role == "operator" and instance.uploaded_by != user:
            raise PermissionDenied("Siz faqat o‘zingiz yuklagan hujjatlarni o‘chira olasiz.")

        filename = instance.file.name if instance.file else "unknown"
        self.perform_destroy(instance)
        logger.info(f"Deleted document: {filename}")
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConsultationFormView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_description="Submit a multi-step consultation form. Use step 1 for patient data, step 2 for medical history, and step 3 for file upload.",
        # --- XATOLIKNI TUZATISH BOSHLANDI ---
        # request_body olib tashlandi, uning o'rniga hamma maydonlar manual_parameters ichida
        manual_parameters=[
            openapi.Parameter(
                name='step',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_INTEGER,
                description='Step number (1, 2, or 3)',
                required=True,
                example=1
            ),
            openapi.Parameter(
                name='patient_data',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description='(Step 1) Serialized JSON object with patient personal data. Example: {"full_name": "John Doe", "phone_number": "+998901234567", ...}',
                required=False
            ),
            openapi.Parameter(
                name='profile_data',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description='(Step 2) Serialized JSON object with medical history. Example: {"complaints": "Fever and cough", "previous_diagnosis": "Cold"}',
                required=False
            ),
            openapi.Parameter(
                name='file',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description='(Step 3) Upload a file (e.g., medical document)',
                required=False
            ),
        ],
        # --- XATOLIKNI TUZATISH TUGADI ---
        responses={
            200: openapi.Response('Success', ApplicationStepSerializer),
            400: 'Bad Request - Invalid step or missing required fields'
        }
    )
    def post(self, request, *args, **kwargs):
        user = request.user
        step = request.data.get("step")
        if not step or not str(step).isdigit() or not 1 <= int(step) <= 3:
            return Response({"error": "Invalid or missing step. Use 1, 2, or 3."}, status=status.HTTP_400_BAD_REQUEST)

        step = int(step) # string dan int ga o'tkazish

        application, created = Application.objects.get_or_create(
            patient=user,
            defaults={"status": "new", "application_id": f"APP_{user.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}"}
        )

        profile, profile_created = PatientProfile.objects.get_or_create(
            user=user,
            defaults={
                "full_name": user.get_full_name() or user.phone_number or "Noma'lum",
                "gender": "male",
                "complaints": "",
                "previous_diagnosis": "",
            }
        )

        if step == 1:
            # So'rovdan kelgan ma'lumotlarni olish (ular endi form-data'da)
            patient_data_str = request.data.get("patient_data")
            if not patient_data_str:
                return Response({"error": "patient_data is required for step 1."}, status=status.HTTP_400_BAD_REQUEST)

            import json
            try:
                patient_data = json.loads(patient_data_str)
            except json.JSONDecodeError:
                return Response({"error": "Invalid JSON format for patient_data."}, status=status.HTTP_400_BAD_REQUEST)

            profile.full_name = patient_data.get("full_name", profile.full_name)
            profile.passport = patient_data.get("passport", profile.passport)
            profile.dob = patient_data.get("dob", profile.dob)
            profile.gender = patient_data.get("gender", profile.gender)
            profile.email = patient_data.get("email", profile.email)
            profile.save()

            user.first_name = patient_data.get("first_name", user.first_name)
            user.last_name = patient_data.get("last_name", user.last_name)
            user.email = patient_data.get("email", user.email)
            user.phone_number = patient_data.get("phone_number", user.phone_number)
            user.save()

        elif step == 2:
            profile_data_str = request.data.get("profile_data")
            if not profile_data_str:
                return Response({"error": "profile_data is required for step 2."}, status=status.HTTP_400_BAD_REQUEST)

            import json
            try:
                profile_data = json.loads(profile_data_str)
            except json.JSONDecodeError:
                return Response({"error": "Invalid JSON format for profile_data."}, status=status.HTTP_400_BAD_REQUEST)

            profile.complaints = profile_data.get("complaints", profile.complaints)
            profile.previous_diagnosis = profile_data.get("previous_diagnosis", profile.previous_diagnosis)
            profile.save()
            application.complaint = profile.complaints
            application.diagnosis = profile.previous_diagnosis
            application.save()

        elif step == 3:
            file = request.FILES.get("file")
            if file:
                # Patient (Medmapp) recordini yaratish
                patient_record, _ = Patient.objects.get_or_create(profile=profile)
                PatientDocument.objects.create(
                    patient=patient_record,
                    file=file,
                    uploaded_by=user,
                    source_type="patient"
                )

        serializer = ApplicationStepSerializer(application, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class PatientAvatarUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_patient_object(self, user):
        if _norm_role(user) != "patient":
            raise PermissionDenied("Faqat bemorlar uchun.")
        profile, created = PatientProfile.objects.get_or_create(
            user=user,
            defaults={
                "full_name": user.get_full_name() or user.phone_number or "Noma'lum",
                "gender": "male",
                "complaints": "",
                "previous_diagnosis": "",
            },
        )
        if created:
            logger.info(f"Created PatientProfile for User {user.id} in PatientAvatarUpdateView")

        patient, patient_created = Patient.objects.get_or_create(
            profile=profile,
            defaults={
                "full_name": user.get_full_name() or user.phone_number,
                "phone": user.phone_number,
                "created_by": user,
            }
        )
        return patient

    @swagger_auto_schema(
        operation_description="Upload or update the patient's avatar.",
        manual_parameters=[
            openapi.Parameter(
                'avatar',
                openapi.IN_FORM,
                description="Avatar image file to upload",
                type=openapi.TYPE_FILE,
                required=True
            )
        ],
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'avatar_url': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_URI)
                }
            )
        }
    )
    def patch(self, request, *args, **kwargs):
        user = request.user
        patient = self.get_patient_object(user)
        if 'avatar' in request.FILES:
            patient.avatar = request.FILES['avatar']
            patient.save(update_fields=['avatar'])
        return Response(
            {"success": True, "avatar_url": request.build_absolute_uri(patient.avatar.url) if patient.avatar else None},
            status=status.HTTP_200_OK
        )

    @swagger_auto_schema(operation_description="Delete the patient's avatar.")
    def delete(self, request, *args, **kwargs):
        user = request.user
        patient = self.get_patient_object(user)
        if patient.avatar:
            patient.avatar.delete(save=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StageListView(generics.ListCreateAPIView):
    queryset = Stage.objects.order_by("order")
    serializer_class = StageSerializer
    permission_classes = [permissions.IsAuthenticated]


class TagListView(generics.ListCreateAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]


class TagDeleteView(generics.DestroyAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_destroy(self, instance):
        logger.info(f"Deleted Tag: {instance.name}")
        super().perform_destroy(instance)


class PatientDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        user = request.user
        if _norm_role(user) != "patient":
            raise PermissionDenied("Faqat bemorlar o'z profilini o'chira oladi.")
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)