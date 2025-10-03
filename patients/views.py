# patients/views.py
import json
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
from .models import Patient, PatientProfile,  PatientDocument
from .serializers import (
    PatientSerializer,
    PatientProfileSerializer,
    PatientDocumentSerializer,
    UserSerializer,
    ApplicationStepSerializer,
)
from applications.models import Application, Document
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
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        if _is_swagger(self) or not self.request.user.is_authenticated:
            logger.info("Swagger or unauthenticated user, returning empty queryset")
            return Patient.objects.none()

        user = self.request.user
        role = _norm_role(user)
        logger.info(f"User: {user.phone_number}, Role: {role}")

        self.create_missing_patients_for_applications()

        queryset = Patient.objects.select_related("profile__user").all()

        if role == "patient":
            queryset = queryset.filter(profile__user=user)
            logger.info(f"Patient records count: {queryset.count()}")
            return queryset

        if role in ["superadmin", "operator"]:
            return queryset

        one_day_ago = timezone.now() - timezone.timedelta(days=1)
        queryset = queryset.filter(created_at__lte=one_day_ago)
        logger.info(f"Filtered patients count (older than 1 day): {queryset.count()}")
        return queryset

    def create_missing_patients_for_applications(self):
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
                },
            )
            if patient_created:
                logger.info(f"Created Patient: {patient.id} for Application {app.id}")
            else:
                patient.full_name = profile.full_name or user.get_full_name() or "Noma'lum"
                patient.save(update_fields=["full_name", ])
                logger.info(f"Updated Patient: {patient.id} for Application {app.id}")

        if created_count > 0:
            logger.info(f"Created {created_count} PatientProfile(s) for Applications")
        else:
            logger.info("No new PatientProfiles created, all exist or updated")




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
        operation_description="Bemor yoki Operator uchun yagona konsultatsiya anketasini yuborish.",
        manual_parameters=[
            openapi.Parameter(
                name='patient_id', in_=openapi.IN_FORM, type=openapi.TYPE_INTEGER, required=False,
                description="MAVJUD bemor uchun so'rov yuborayotganda operator tomonidan ishlatiladi."
            ),
            openapi.Parameter(
                name='patient_data', in_=openapi.IN_FORM, type=openapi.TYPE_STRING, required=False,
                description='YANGI bemor uchun JSON formatidagi shaxsiy ma\'lumotlar (ichida "phone_number" bo\'lishi shart).'
            ),
            openapi.Parameter(
                name='profile_data', in_=openapi.IN_FORM, type=openapi.TYPE_STRING, required=False,
                description='Tibbiy ma\'lumotlar (shikoyatlar, avvalgi tashxis).'
            ),
            openapi.Parameter(
                name='file', in_=openapi.IN_FORM, type=openapi.TYPE_FILE, required=False,
                description='Tibbiy hujjat (tahlil, rentgen va hk).'
            ),
        ],
        request_body=None,
        responses={200: ApplicationSerializer, 400: 'Xato so\'rov'}
    )
    def post(self, request, *args, **kwargs):
        requesting_user = request.user
        patient_user = None

        if getattr(requesting_user, 'role', 'user') in ['operator', 'admin']:
            patient_id = request.data.get("patient_id")
            patient_data_str = request.data.get("patient_data")

            if patient_id:
                patient_user = get_object_or_404(User, id=patient_id, role='user')
            elif patient_data_str:
                try:
                    patient_data = json.loads(patient_data_str)
                    phone_number = patient_data.get("phone_number")
                    if not phone_number:
                        return Response({"error": "Yangi bemor uchun 'patient_data' ichida telefon raqami majburiy."}, status=status.HTTP_400_BAD_REQUEST)

                    patient_user, _ = User.objects.get_or_create(
                        phone_number=phone_number,
                        defaults={'phone_number': phone_number, 'role': 'user'}
                    )
                except json.JSONDecodeError:
                    return Response({"error": "'patient_data' noto'g'ri JSON formatida."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"error": "Operator uchun 'patient_id' (mavjud bemor uchun) yoki 'patient_data' (yangi bemor uchun) majburiy."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            patient_user = requesting_user

        application, _ = Application.objects.get_or_create(patient=patient_user)
        profile, _ = PatientProfile.objects.get_or_create(user=patient_user)

        patient_data_str = request.data.get("patient_data")
        if patient_data_str:
            try:
                patient_data = json.loads(patient_data_str)
                profile.full_name = patient_data.get("full_name", profile.full_name)
                profile.passport = patient_data.get("passport", profile.passport)
                profile.dob = patient_data.get("dob", profile.dob)
                profile.gender = patient_data.get("gender", profile.gender)
                profile.email = patient_data.get("email", profile.email)
                profile.save()

                patient_user.first_name = patient_data.get("first_name", patient_user.first_name)
                patient_user.last_name = patient_data.get("last_name", patient_user.last_name)
                patient_user.email = patient_data.get("email", patient_user.email)
                patient_user.save()
            except json.JSONDecodeError:
                pass

        profile_data_str = request.data.get("profile_data")
        if profile_data_str:
            try:
                data = json.loads(profile_data_str)
                profile.complaints = data.get('complaints', profile.complaints)
                profile.previous_diagnosis = data.get('previous_diagnosis', profile.previous_diagnosis)
                profile.save()
                application.complaint = profile.complaints
                application.diagnosis = data.get('previous_diagnosis', application.diagnosis)
                application.save()

            except json.JSONDecodeError:
                pass

        file = request.FILES.get("file")
        if file:
            patient_record, _ = Patient.objects.get_or_create(profile=profile)
            PatientDocument.objects.create(
                patient=patient_record,
                file=file,
                uploaded_by=requesting_user,
                source_type="operator" if getattr(requesting_user, 'role', 'user') != 'user' else "patient"
            )

        serializer = ApplicationSerializer(application, context={"request": request})
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






class PatientDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        user = request.user
        if _norm_role(user) != "patient":
            raise PermissionDenied("Faqat bemorlar o'z profilini o'chira oladi.")
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)