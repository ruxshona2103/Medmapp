# serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Patient, PatientProfile, Stage, Tag, PatientHistory, PatientDocument

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    # QO'SHILDI: Foydalanuvchining to'liq ismini chiqarish uchun
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        # O'ZGARTIRILDI: 'full_name' ro'yxatga qo'shildi
        fields = ["id", "first_name", "last_name", "full_name", "role", "phone_number"]
        ref_name = "PatientsUserSerializer"

    # QO'SHILDI: get_full_name metodi
    def get_full_name(self, obj):
        return obj.get_full_name()


class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = ["id", "title", "code_name", "order", "color"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "color"]


class PatientHistorySerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = PatientHistory
        fields = ["id", "author", "comment", "created_at"]


class PatientDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)
    source_type_display = serializers.CharField(
        source="get_source_type_display", read_only=True
    )

    class Meta:
        model = PatientDocument
        fields = [
            "id",
            "file",
            "description",
            "uploaded_by",
            "uploaded_at",
            "source_type",
            "source_type_display",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if instance.file and request:
            data["file"] = request.build_absolute_uri(instance.file.url)
        return data


from rest_framework import serializers
from .models import Patient  # o'z model joylashgan faylini to‘g‘ri chaqir


class PatientSerializer(serializers.ModelSerializer):
    # Related fieldlarni o‘qish uchun
    stage_title = serializers.CharField(source="stage.title", read_only=True)
    tag_name = serializers.CharField(source="tag.name", read_only=True)
    tag_color = serializers.CharField(source="tag.color", read_only=True)

    # Avatar uchun to‘liq URL
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            "id",
            "full_name",
            "phone",
            "email",
            "source",
            "stage_title",
            "tag_name",
            "tag_color",
            "created_at",
            "updated_at",
            "avatar_url",  # yangi maydon
        ]

    def get_avatar_url(self, obj):
        """
        Avatarning to‘liq URL manzilini qaytaradi.
        request context bo‘lsa, build_absolute_uri ishlatiladi.
        """
        request = self.context.get("request")
        if obj.avatar and request:
            return request.build_absolute_uri(obj.avatar.url)
        return None


class PatientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    # Endi 'patient' nested serializeri avatarni ham qaytaradi
    patient = PatientSerializer(source="patient_record", read_only=True)
    documents = PatientDocumentSerializer(
        many=True, read_only=True, source="patient_record.documents"
    )
    history = PatientHistorySerializer(
        many=True, read_only=True, source="patient_record.history"
    )

    full_name = serializers.CharField(max_length=150, write_only=True, required=False)

    class Meta:
        model = PatientProfile
        fields = [
            "id",
            "user",
            "passport",
            "dob",
            "gender",
            "complaints",
            "previous_diagnosis",
            "patient",
            "documents",
            "history",
            "full_name",
        ]

    def update(self, instance, validated_data):
        # ... (bu qism o'zgarishsiz qoladi) ...
        full_name = validated_data.pop("full_name", None)
        user = instance.user

        if full_name:
            parts = full_name.split(" ", 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ""
            user.save(update_fields=["first_name", "last_name"])

            if hasattr(instance, "patient_record") and instance.patient_record:
                patient = instance.patient_record
                patient.full_name = full_name
                patient.save(update_fields=["full_name"])

        return super().update(instance, validated_data)


class PatientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    patient = PatientSerializer(source="patient_record", read_only=True)
    documents = PatientDocumentSerializer(
        many=True, read_only=True, source="patient_record.documents"
    )
    history = PatientHistorySerializer(
        many=True, read_only=True, source="patient_record.history"
    )

    # QO'SHILDI: To'liq ismni PATCH so'rovida qabul qilish uchun (faqat yozish uchun)
    full_name = serializers.CharField(max_length=150, write_only=True, required=False)

    class Meta:
        model = PatientProfile
        # O'ZGARTIRILDI: 'full_name' maydoni qo'shildi
        fields = [
            "id",
            "user",
            "passport",
            "dob",
            "gender",
            "complaints",
            "previous_diagnosis",
            "patient",
            "documents",
            "history",
            "full_name",  # Yangi maydon'
        ]

    # QO'SHILDI: update metodi to'liq ismni yangilash uchun
    def update(self, instance, validated_data):
        """
        To'liq ismni (full_name) yangilash logikasi.
        Bu metod User modelidagi first_name/last_name va agar mavjud bo'lsa,
        bog'liq Patient modelidagi full_name maydonlarini yangilaydi.
        """
        # 'full_name' maydonini validated_data'dan olamiz
        full_name = validated_data.pop("full_name", None)
        user = instance.user

        if full_name:
            # Ismni probel bo'yicha ajratamiz (ism va familiyaga)
            parts = full_name.split(" ", 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ""
            user.save(update_fields=["first_name", "last_name"])

            # Agar profilga bog'langan bemor (patient_record) mavjud bo'lsa, uning ham ismini yangilaymiz
            if hasattr(instance, "patient_record") and instance.patient_record:
                patient = instance.patient_record
                patient.full_name = full_name
                patient.save(update_fields=["full_name"])

        # Boshqa maydonlarni standart usulda yangilash uchun super().update() chaqiriladi
        return super().update(instance, validated_data)


class PatientAvatarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ["avatar"]
        extra_kwargs = {
            "avatar": {"required": True}  # Patch so'rovida avatar yuborilishi shart
        }
