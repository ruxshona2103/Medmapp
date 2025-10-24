from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Application, ApplicationHistory, Document
from patients.models import Patient
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
# 📎 DOCUMENT SERIALIZER - Clean va strukturali
# ===============================================================
class DocumentSerializer(serializers.ModelSerializer):
    """Hujjat serializer - to'liq ma'lumotlar bilan"""
    uploaded_by = UserMinimalSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    file_type = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id',
            'file',
            'file_url',
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
        """Fayl turi (pdf, jpg, png)"""
        if obj.file:
            name = obj.file.name
            ext = os.path.splitext(name)[1].lower()
            return ext.replace('.', '') if ext else None
        return None


# ===============================================================
# 🔹 PATIENT SERIALIZER (minimal)
# ===============================================================
class PatientMinimalSerializer(serializers.ModelSerializer):
    """Bemor minimal ma'lumotlari"""

    class Meta:
        model = Patient
        fields = ['id', 'full_name', 'phone_number', 'date_of_birth', 'gender']


# ===============================================================
# 🔹 STAGE SERIALIZER (minimal)
# ===============================================================
class StageMinimalSerializer(serializers.ModelSerializer):
    """Bosqich minimal ma'lumotlari"""

    class Meta:
        model = Stage
        fields = ['id', 'title', 'order']


# ===============================================================
# 🩺 APPLICATION SERIALIZER - Asosiy (TUZATILGAN)
# ===============================================================
class ApplicationSerializer(serializers.ModelSerializer):
    """Ariza to'liq ma'lumotlari"""
    patient = PatientMinimalSerializer(read_only=True)
    stage = StageMinimalSerializer(read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)
    history = serializers.SerializerMethodField()

    # Qo'shimcha hisoblangan maydonlar
    documents_count = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            'id',
            'application_id',
            'patient',
            'clinic_name',
            'complaint',
            'diagnosis',
            'final_conclusion',
            'stage',
            'status',
            'status_display',
            'comment',
            'documents',
            'documents_count',
            'history',
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
            'status_display',
        ]

    def get_documents_count(self, obj):
        """Hujjatlar soni"""
        return obj.documents.count()

    def get_status_display(self, obj):
        """Status nomi (human-readable)"""
        status_map = {
            'new': 'Yangi',
            'in_progress': 'Jarayonda',
            'completed': 'Tugatilgan',
            'rejected': 'Rad etilgan',
        }
        return status_map.get(obj.status, obj.status)

    def get_history(self, obj):
        """
        Tarix - ApplicationHistory model orqali
        ✅ TUZATILGAN: applicationhistory_set xatosi bartaraf etildi
        """
        try:
            # Method 1: ApplicationHistory model orqali (ENG ISHONCHLI)
            history = ApplicationHistory.objects.filter(
                application=obj
            ).select_related('author').order_by('-created_at')[:10]
            return ApplicationHistorySerializer(history, many=True).data
        except Exception as e:
            # Agar xato bo'lsa, bo'sh array qaytarish
            return []


# ===============================================================
# ✏️ APPLICATION CREATE/UPDATE SERIALIZER
# ===============================================================
class ApplicationCreateUpdateSerializer(serializers.ModelSerializer):
    """Ariza yaratish va tahrirlash"""
    patient_id = serializers.IntegerField(write_only=True, required=True)
    stage_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    # ✅ Qo'shimcha - response'da ko'rsatish uchun
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
        """Yangi ariza yaratish"""
        patient_id = validated_data.pop('patient_id')
        stage_id = validated_data.pop('stage_id', None)

        patient = Patient.objects.get(id=patient_id)

        # Ariza yaratish
        application = Application.objects.create(
            patient=patient,
            **validated_data
        )

        # Agar stage berilgan bo'lsa
        if stage_id:
            stage = Stage.objects.get(id=stage_id)
            application.stage = stage
            application.save()

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
                pass  # History model yo'q bo'lsa, xato bermaydi

        return application

    def update(self, instance, validated_data):
        """Arizani yangilash"""
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

        # Boshqa maydonlarni yangilash
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
                    comment="🔄 Ariza ma'lumotlari yangilandi"
                )
            except:
                pass  # History model yo'q bo'lsa, xato bermaydi

        return instance


# ===============================================================
# 🧾 COMPLETED APPLICATION SERIALIZER - Operator paneli (TUZATILGAN)
# ===============================================================
class CompletedApplicationSerializer(serializers.ModelSerializer):
    """Tugatilgan va rad etilgan arizalar"""
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    phone_number = serializers.CharField(source='patient.phone_number', read_only=True)
    clinic = serializers.CharField(source='clinic_name', read_only=True)
    status_label = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    documents = DocumentSerializer(many=True, read_only=True)
    history = serializers.SerializerMethodField()  # ✅ TUZATILGAN

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
            'documents',
            'history',
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
        """Status nomi (frontend uchun)"""
        status_map = {
            'completed': 'Tugatilgan',
            'rejected': 'Rad etilgan',
        }
        return status_map.get(obj.status, obj.status)

    def get_date(self, obj):
        """DateTime'ni Date formatiga o'tkazish"""
        if obj.updated_at:
            return obj.updated_at.strftime('%Y-%m-%d')
        return None

    def get_history(self, obj):
        """
        Tarix - ApplicationHistory model orqali
        ✅ TUZATILGAN: applicationhistory_set xatosi bartaraf etildi
        """
        try:
            history = ApplicationHistory.objects.filter(
                application=obj
            ).select_related('author').order_by('-created_at')[:10]
            return ApplicationHistorySerializer(history, many=True).data
        except:
            return []


# ===============================================================
# 🔹 PATIENT DETAIL SERIALIZER (to'liq ma'lumotlar) - TUZATILGAN
# ===============================================================
class PatientDetailSerializer(serializers.ModelSerializer):
    """
    Bemor to'liq ma'lumotlari - applications va documents bilan
    ⚠️ Bu serializer patients/serializers.py da bo'lishi kerak!
    Lekin circular import'dan qochish uchun bu yerda ham qoldirildi
    """
    applications = serializers.SerializerMethodField()
    total_applications = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            'id',
            'full_name',
            'phone_number',
            'date_of_birth',
            'gender',
            'email',
            'avatar',
            'complaints',
            'previous_diagnosis',
            'applications',
            'total_applications',
            'created_at',
            'updated_at',
        ]

    def get_applications(self, obj):
        """Bemorning arizalari - documents bilan"""
        applications = Application.objects.filter(
            patient=obj,
            is_archived=False
        ).select_related('stage').prefetch_related('documents').order_by('-created_at')

        # ApplicationSerializer'dan foydalanish
        return ApplicationSerializer(applications, many=True, context=self.context).data

    def get_total_applications(self, obj):
        """Jami arizalar soni"""
        return Application.objects.filter(patient=obj, is_archived=False).count()