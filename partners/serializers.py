# partners/serializers.py
# ===============================================================
# HAMKOR PANEL - SERIALIZERS (MAXFIY MA'LUMOTLARSIZ!)
# ===============================================================

from rest_framework import serializers
from .models import Partner, PartnerResponseDocument
from patients.models import Patient, PatientDocument
from applications.models import Application
from core.models import Stage, Tag


# ===============================================================
# PATIENT SERIALIZERS - Maxfiy ma'lumotlarsiz
# ===============================================================

class PartnerPatientDocumentSerializer(serializers.ModelSerializer):
    """
    Bemor hujjatlari - faqat file ma'lumotlari

    ❌ Maxfiy ma'lumotlar yo'q
    """
    file_url = serializers.SerializerMethodField()
    file_size_mb = serializers.SerializerMethodField()

    class Meta:
        model = PatientDocument
        fields = [
            'id',
            'file_name',
            'file_url',
            'file_size_mb',
            'uploaded_at',
        ]

    def get_file_url(self, obj):
        """File URL"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_file_size_mb(self, obj):
        """File size (MB)"""
        if obj.file:
            return round(obj.file.size / (1024 * 1024), 2)
        return 0


class PartnerApplicationSerializer(serializers.ModelSerializer):
    """
    Arizalar - faqat asosiy ma'lumotlar

    ❌ Maxfiy ma'lumotlar yo'q
    """
    stage_name = serializers.CharField(source='stage.title', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Application
        fields = [
            'id',
            'application_id',
            'clinic_name',
            'desired_surgery_date',
            'status',
            'status_display',
            'stage_name',
            'created_at',
        ]


class PartnerResponseDocumentSerializer(serializers.ModelSerializer):
    """
    Hamkor javob xatlari serializer
    """
    file_url = serializers.SerializerMethodField()
    partner_name = serializers.CharField(source='partner.name', read_only=True)

    class Meta:
        model = PartnerResponseDocument
        fields = [
            'id',
            'partner_name',
            'file_name',
            'file_url',
            'title',
            'description',
            'document_type',
            'uploaded_at',
        ]

    def get_file_url(self, obj):
        """File URL"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class PartnerPatientListSerializer(serializers.ModelSerializer):
    """
    Bemorlar ro'yxati - Hamkor paneli uchun

    ✅ Faqat ruxsat etilgan ma'lumotlar:
    - ID
    - Ism-Familiya
    - Bosqich
    - Tag
    - Oxirgi yangilanish

    ❌ MAXFIY MA'LUMOTLAR YO'Q:
    - Pasport
    - Telefon
    - Email
    - Tug'ilgan sana
    - Manzil
    """
    stage_name = serializers.CharField(source='stage.title', read_only=True)
    stage_code = serializers.CharField(source='stage.code', read_only=True)
    tag_name = serializers.CharField(source='tag.name', read_only=True, allow_null=True)
    applications_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Patient
        fields = [
            'id',
            'full_name',  # ✅ Ruxsat etilgan
            'gender',  # ✅ Ruxsat etilgan
            'stage_name',
            'stage_code',
            'tag_name',
            'applications_count',
            'created_at',
            'updated_at',
        ]
        # ❌ EXCLUDE qilingan (ko'rinmaydi):
        # passport, phone_number, email, date_of_birth, address, etc.


class PartnerPatientDetailSerializer(serializers.ModelSerializer):
    """
    Bemorning batafsil ma'lumotlari - Hamkor paneli uchun

    ✅ Faqat ruxsat etilgan ma'lumotlar:
    - Ism-Familiya
    - Tibbiy ma'lumotlar
    - Hujjatlar
    - Arizalar
    - Hamkor javoblari

    ❌ MAXFIY MA'LUMOTLAR YO'Q:
    - Pasport, telefon, email, address, tug'ilgan sana
    """
    stage_name = serializers.CharField(source='stage.title', read_only=True)
    stage_code = serializers.CharField(source='stage.code', read_only=True)
    tag_name = serializers.CharField(source='tag.name', read_only=True, allow_null=True)

    # Nested serializers
    documents = PartnerPatientDocumentSerializer(many=True, read_only=True)
    applications = PartnerApplicationSerializer(many=True, read_only=True)
    partner_responses = PartnerResponseDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Patient
        fields = [
            'id',
            'full_name',  # ✅ Ruxsat etilgan
            'gender',  # ✅ Ruxsat etilgan

            # Tibbiy ma'lumotlar (ruxsat etilgan)
            'complaints',
            'previous_diagnosis',
            'current_medications',
            'allergies',
            'chronic_diseases',

            # Bosqich va tag
            'stage_name',
            'stage_code',
            'tag_name',

            # Nested data
            'documents',
            'applications',
            'partner_responses',

            # Timestamps
            'created_at',
            'updated_at',
        ]
        # ❌ EXCLUDE qilingan (maxfiy):
        # passport, phone_number, email, date_of_birth, address,
        # created_by, contract_file, response_letter, etc.


# ===============================================================
# STAGE CHANGE SERIALIZER
# ===============================================================

class PartnerStageChangeSerializer(serializers.Serializer):
    """
    Bosqichni o'zgartirish

    Hamkor bemorni bir bosqichdan ikkinchisiga o'tkazishi mumkin.
    """
    new_stage = serializers.CharField(
        required=True,
        help_text='Yangi bosqich kodi (masalan: stage_response)'
    )

    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Izoh (tarixga yoziladi)'
    )

    def validate_new_stage(self, value):
        """Bosqich mavjudligini tekshirish"""
        try:
            stage = Stage.objects.get(code=value)
        except Stage.DoesNotExist:
            raise serializers.ValidationError(f"Bosqich '{value}' topilmadi")
        return value


# ===============================================================
# RESPONSE DOCUMENT UPLOAD SERIALIZER
# ===============================================================
class PartnerResponseUploadSerializer(serializers.ModelSerializer):
    """
    Javob xati yuklash (hamkor tomonidan)
    """

    class Meta:
        model = PartnerResponseDocument
        fields = ['file', 'title', 'description', 'document_type']
        extra_kwargs = {
            'file': {'required': True},
            'title': {'required': False, 'allow_blank': True},
            'description': {'required': False, 'allow_blank': True},
            'document_type': {'required': False},
        }

    def validate_file(self, value):
        """File hajmini tekshirish (max 10MB)"""
        max_size = 10 * 1024 * 1024  # 10 MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"Fayl hajmi {max_size / (1024 * 1024)}MB dan oshmasligi kerak"
            )
        return value

    def create(self, validated_data):
        """
        ✅ Bemor va hamkorni kontekstdan olish
        (upload_response view ichida context orqali yuboriladi)
        """
        patient = self.context.get("patient")
        partner = self.context.get("partner")

        if not patient or not partner:
            raise serializers.ValidationError("Patient yoki Partner kontekstdan topilmadi.")

        document = PartnerResponseDocument.objects.create(
            patient=patient,
            partner=partner,
            **validated_data
        )
        return document


# ===============================================================
# PARTNER PROFILE SERIALIZER
# ===============================================================

class PartnerProfileSerializer(serializers.ModelSerializer):
    """
    Hamkor profili

    Hamkor o'z profil ma'lumotlarini ko'rishi uchun.
    """
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Partner
        fields = [
            'id',
            'username',
            'email',
            'name',
            'code',
            'specialization',
            'contact_person',
            'phone',
            'total_patients',
            'active_patients',
            'is_active',
            'created_at',
        ]
        read_only_fields = [
            'code',
            'total_patients',
            'active_patients',
            'created_at',
        ]


