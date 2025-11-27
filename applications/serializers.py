# applications/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Application, ApplicationHistory, Document
from patients.models import Patient, PatientDocument
from core.models import Stage
import os

User = get_user_model()


# ===============================================================
# 👤 USER SERIALIZER - Minimal ma'lumot
# ===============================================================
class UserMinimalSerializer(serializers.ModelSerializer):
    """Foydalanuvchi minimal ma'lumotlari"""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "full_name", "phone_number"]

    def get_full_name(self, obj):
        """To'liq ism"""
        if hasattr(obj, 'get_full_name') and callable(obj.get_full_name):
            return obj.get_full_name()
        elif hasattr(obj, 'full_name'):
            return obj.full_name
        else:
            first = getattr(obj, 'first_name', '')
            last = getattr(obj, 'last_name', '')
            return f"{first} {last}".strip() or getattr(obj, 'username', 'Unknown')


# ===============================================================
# 🕓 APPLICATION HISTORY SERIALIZER
# ===============================================================
class ApplicationHistorySerializer(serializers.ModelSerializer):
    """Ariza tarixi"""
    author = UserMinimalSerializer(read_only=True)

    class Meta:
        model = ApplicationHistory
        fields = ['id', 'author', 'comment', 'created_at']
        read_only_fields = ['id', 'author', 'created_at']


# ===============================================================
# 📎 DOCUMENT SERIALIZER
# ===============================================================
class DocumentSerializer(serializers.ModelSerializer):
    """Hujjat serializer - to'liq ma'lumotlar"""
    uploaded_by = UserMinimalSerializer(read_only=True)
    file = serializers.FileField(write_only=True)  # ✅ Faqat upload uchun
    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    file_type = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id',
            'file',  # ✅ Write only - faqat upload uchun
            'file_url',  # ✅ Read only - response uchun
            'file_name',
            'file_size',
            'file_type',
            'description',
            'uploaded_by',
            'uploaded_at',
        ]
        read_only_fields = ['id', 'uploaded_at', 'file_url', 'file_name', 'file_size', 'file_type', 'uploaded_by']

    def get_file_url(self, obj):
        """To'liq URL"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_file_name(self, obj):
        """Fayl nomi"""
        if obj.file:
            return os.path.basename(obj.file.name)
        return None

    def get_file_size(self, obj):
        """Fayl hajmi (bytes)"""
        if obj.file:
            try:
                return obj.file.size
            except:
                return None
        return None

    def get_file_type(self, obj):
        """Fayl turi"""
        if obj.file:
            name = obj.file.name
            ext = os.path.splitext(name)[1].lower()
            return ext.replace('.', '') if ext else None
        return None


# ===============================================================
# 🔹 PATIENT MINIMAL SERIALIZER
# ===============================================================
class PatientMinimalSerializer(serializers.ModelSerializer):
    """Bemor minimal ma'lumotlari"""

    class Meta:
        model = Patient
        fields = [
            'id',
            'full_name',
            'phone_number',
            'date_of_birth',
            'gender',
            'email',
            'complaints',  # ✅ QOSHILDI
            'previous_diagnosis',  # ✅ QOSHILDI
        ]


# ===============================================================
# 🔹 STAGE SERIALIZER
# ===============================================================
class StageMinimalSerializer(serializers.ModelSerializer):
    """Bosqich minimal ma'lumotlari"""

    class Meta:
        model = Stage
        fields = ['id', 'title', 'order']


# ===============================================================
# 🩺 APPLICATION SERIALIZER - ASOSIY
# ===============================================================
class ApplicationSerializer(serializers.ModelSerializer):
    """
    Ariza to'liq ma'lumotlari

    ✅ QOSHILDI:
    - documents (DocumentSerializer bilan) - Arizaga yuklangan hujjatlar
    - patient_documents (PatientDocumentSerializer bilan) - Bemor anketa to'ldirganda yuklagan hujjatlar
    - history (ApplicationHistorySerializer bilan)
    - patient.complaints
    - patient.previous_diagnosis
    """
    patient = PatientMinimalSerializer(read_only=True)
    stage = StageMinimalSerializer(read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)  # ✅ Arizaga yuklangan hujjatlar
    patient_documents = serializers.SerializerMethodField()  # ✅ YANGI - Bemor hujjatlari
    history = serializers.SerializerMethodField()  # ✅ QOSHILDI

    # Qo'shimcha maydonlar
    documents_count = serializers.SerializerMethodField()
    patient_documents_count = serializers.SerializerMethodField()  # ✅ YANGI
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            'id',
            'application_id',
            'patient',  # ✅ complaints bilan
            'clinic_name',
            'complaint',
            'diagnosis',
            'final_conclusion',
            'stage',
            'status',
            'status_display',
            'comment',
            'documents',  # ✅ Arizaga yuklangan hujjatlar
            'documents_count',
            'patient_documents',  # ✅ YANGI - Bemor anketa hujjatlari
            'patient_documents_count',  # ✅ YANGI
            'history',  # ✅ QOSHILDI
            'created_at',
            'updated_at',
            'is_archived',
        ]
        read_only_fields = [
            'id',
            'application_id',
            'created_at',
            'updated_at',
            'documents_count',
            'patient_documents_count',
            'status_display',
        ]

    def get_documents_count(self, obj):
        """Arizaga yuklangan hujjatlar soni"""
        return obj.documents.count()

    def get_patient_documents(self, obj):
        """
        ✅ YANGI - Bemor anketa to'ldirganda yuklagan hujjatlar

        Bu metod bemorning barcha hujjatlarini qaytaradi
        (PatientDocument model)
        """
        try:
            # ✅ Circular import oldini olish uchun local import
            from patients.serializers import PatientDocumentSerializer

            patient_docs = PatientDocument.objects.filter(
                patient=obj.patient
            ).select_related('uploaded_by').order_by('-uploaded_at')
            return PatientDocumentSerializer(patient_docs, many=True, context=self.context).data
        except:
            return []

    def get_patient_documents_count(self, obj):
        """Bemor hujjatlari soni"""
        try:
            return PatientDocument.objects.filter(patient=obj.patient).count()
        except:
            return 0

    def get_status_display(self, obj):
        """Status nomi"""
        status_map = {
            'new': 'Yangi',
            'in_progress': 'Jarayonda',
            'completed': 'Tugatilgan',
            'rejected': 'Rad etilgan',
        }
        return status_map.get(obj.status, obj.status)

    def get_history(self, obj):
        """
        ✅ QOSHILDI - Tarix

        ApplicationHistory model orqali tarixni olish
        """
        try:
            history = ApplicationHistory.objects.filter(
                application=obj
            ).select_related('author').order_by('-created_at')[:10]
            return ApplicationHistorySerializer(history, many=True).data
        except:
            return []

    def to_representation(self, instance):
        """
        ✅ Response'ni to'g'rilash

        Garantiya qilish:
        - complaint har doim qaytadi
        - documents har doim qaytadi
        """
        data = super().to_representation(instance)

        # ✅ complaint ni garantiya qilish
        if not data.get('complaint'):
            data['complaint'] = instance.complaint or ''

        return data


# ===============================================================
# ✏️ APPLICATION CREATE/UPDATE SERIALIZER
# ===============================================================
class ApplicationCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Ariza yaratish va tahrirlash

    ✅ QOSHILDI:
    - to_representation metodi (ApplicationSerializer formatda response)
    - documents field (file upload)
    - patient.complaints yangilash
    """
    patient_id = serializers.IntegerField(write_only=True, required=True)
    stage_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    # ✅ TO'G'RILANDI - Swagger uchun
    # documents field olib tashlandi - alohida API orqali yuklash kerak
    # POST /applications/{id}/documents/ - document yuklash uchun

    # Response uchun
    patient = PatientMinimalSerializer(read_only=True)
    stage = StageMinimalSerializer(read_only=True)

    class Meta:
        model = Application
        fields = [
            'id',
            'application_id',
            'patient_id',
            'patient',
            'clinic_name',
            'complaint',
            'diagnosis',
            'final_conclusion',
            'stage_id',
            'stage',
            'status',
            'comment',
            # 'documents' - OLIB TASHLANDI (alohida API orqali yuklash)
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'application_id', 'patient', 'stage', 'created_at', 'updated_at']

    def validate_patient_id(self, value):
        """Bemor mavjudligini tekshirish"""
        if not Patient.objects.filter(id=value).exists():
            raise serializers.ValidationError("Bemor topilmadi")
        return value

    def validate_stage_id(self, value):
        """Bosqich mavjudligini tekshirish"""
        if value and not Stage.objects.filter(id=value).exists():
            raise serializers.ValidationError("Bosqich topilmadi")
        return value

    def create(self, validated_data):
        """
        ✅ Yangi ariza yaratish

        Documents ALOHIDA yuklash kerak:
        POST /api/applications/{id}/documents/
        """
        patient_id = validated_data.pop('patient_id')
        stage_id = validated_data.pop('stage_id', None)

        complaint = validated_data.get('complaint', '')

        patient = Patient.objects.get(id=patient_id)

        # Ariza yaratish
        application = Application.objects.create(
            patient=patient,
            **validated_data
        )

        # Stage qo'shish
        if stage_id:
            stage = Stage.objects.get(id=stage_id)
            application.stage = stage
            application.save()

        # ✅ Patient.complaints yangilash
        if complaint:
            patient.complaints = complaint
            patient.save()

        # Tarixga yozish
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            try:
                ApplicationHistory.objects.create(
                    application=application,
                    author=request.user,
                    comment="📝 Yangi ariza yaratildi"
                )
            except:
                pass

        return application

    def update(self, instance, validated_data):
        """
        ✅ Arizani yangilash

        Documents ALOHIDA yuklash kerak:
        POST /api/applications/{id}/documents/
        """
        patient_id = validated_data.pop('patient_id', None)
        stage_id = validated_data.pop('stage_id', None)

        # Bemorni yangilash
        if patient_id:
            patient = Patient.objects.get(id=patient_id)
            instance.patient = patient

        # Bosqichni yangilash
        if stage_id:
            stage = Stage.objects.get(id=stage_id)
            instance.stage = stage

        # Boshqa maydonlar
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # Tarixga yozish
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            try:
                ApplicationHistory.objects.create(
                    application=instance,
                    author=request.user,
                    comment="🔄 Ariza yangilandi"
                )
            except:
                pass

        return instance

    def to_representation(self, instance):
        """
        ✅ QOSHILDI - Response ApplicationSerializer formatda

        Bu metod response'ni ApplicationSerializer formatida qaytaradi:
        - patient (complaints bilan)
        - documents list
        - history list
        """
        return ApplicationSerializer(instance, context=self.context).data


# ===============================================================
# 🧾 COMPLETED APPLICATION SERIALIZER
# ===============================================================
class CompletedApplicationSerializer(serializers.ModelSerializer):
    """Tugatilgan va rad etilgan arizalar"""
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    phone_number = serializers.CharField(source='patient.phone_number', read_only=True)
    clinic = serializers.CharField(source='clinic_name', read_only=True)
    status_label = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    documents = DocumentSerializer(many=True, read_only=True)  # ✅ Arizaga yuklangan hujjatlar
    patient_documents = serializers.SerializerMethodField()  # ✅ YANGI - Bemor hujjatlari
    history = serializers.SerializerMethodField()  # ✅ QOSHILDI

    class Meta:
        model = Application
        fields = [
            'id',
            'application_id',
            'patient_name',
            'phone_number',
            'clinic',
            'complaint',
            'diagnosis',
            'final_conclusion',
            'status',
            'status_label',
            'date',
            'documents',  # ✅ Arizaga yuklangan hujjatlar
            'patient_documents',  # ✅ YANGI - Bemor anketa hujjatlari
            'history',  # ✅ QOSHILDI
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'application_id',
            'patient_name',
            'phone_number',
            'clinic',
            'status_label',
            'date',
            'created_at',
            'updated_at',
        ]

    def get_status_label(self, obj):
        """Status nomi"""
        status_map = {
            'completed': 'Tugatilgan',
            'rejected': 'Rad etilgan',
        }
        return status_map.get(obj.status, obj.status)

    def get_date(self, obj):
        """Sana"""
        if obj.updated_at:
            return obj.updated_at.strftime('%Y-%m-%d')
        return None

    def get_patient_documents(self, obj):
        """
        ✅ YANGI - Bemor anketa to'ldirganda yuklagan hujjatlar
        """
        try:
            # ✅ Circular import oldini olish uchun local import
            from patients.serializers import PatientDocumentSerializer

            patient_docs = PatientDocument.objects.filter(
                patient=obj.patient
            ).select_related('uploaded_by').order_by('-uploaded_at')
            return PatientDocumentSerializer(patient_docs, many=True, context=self.context).data
        except:
            return []

    def get_history(self, obj):
        """
        ✅ QOSHILDI - Tarix
        """
        try:
            history = ApplicationHistory.objects.filter(
                application=obj
            ).select_related('author').order_by('-created_at')[:10]
            return ApplicationHistorySerializer(history, many=True).data
        except:
            return []