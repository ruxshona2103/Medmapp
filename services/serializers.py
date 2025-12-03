from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from patients.models import Patient
from core.models import Tag
from .models import (
    VisaRequest,
    TransferRequest,
    TranslatorRequest,
    SimCardRequest,
    Hotel,
    Booking,
)

# ===============================================================
# 🔒 Safe Model Serializer
# ===============================================================
class SafeModelSerializer(serializers.ModelSerializer):
    """
    Model ichidagi clean() metodini avtomatik chaqirib tekshiradi.
    """
    def validate(self, attrs):
        instance = self.Meta.model(**attrs)
        try:
            if hasattr(instance, "clean"):
                instance.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict or e.messages)
        return attrs


# ===============================================================
# 🛂 VISA REQUEST
# ===============================================================
class VisaRequestSerializer(serializers.ModelSerializer):
    passport_scan_url = serializers.SerializerMethodField()
    patient_id = serializers.SerializerMethodField()
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        required=False,
        allow_empty=True
    )

    class Meta:
        model = VisaRequest
        fields = [
            "id", "passport_scan", "passport_scan_url",
            "note", "tags", "created_at", "patient_id"
        ]
        read_only_fields = ["id", "created_at", "patient_id"]

    def get_passport_scan_url(self, obj):
        request = self.context.get("request")
        if obj.passport_scan and request:
            return request.build_absolute_uri(obj.passport_scan.url)
        return None

    def get_patient_id(self, obj):
        patient = Patient.objects.filter(created_by=obj.user).first()
        return patient.id if patient else None

    def create(self, validated_data):
        user = self.context["request"].user
        tags_data = validated_data.pop('tags', None)

        visa_request = VisaRequest.objects.create(user=user, **validated_data)

        # ✅ Agar tags berilmagan bo'lsa, default "new" tag ni qo'shish
        if tags_data is None or len(tags_data) == 0:
            default_tag = Tag.objects.filter(code_name='new').first()
            if default_tag:
                visa_request.tags.set([default_tag])
        else:
            visa_request.tags.set(tags_data)

        return visa_request

    def update(self, instance, validated_data):
        tags_data = validated_data.pop('tags', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # ✅ Tagsni to'liq almashtirish (faqat kelgan taglar qoladi)
        if tags_data is not None:
            instance.tags.set(tags_data)

        return instance


# ===============================================================
# ✈️ TRANSFER REQUEST
# ===============================================================
class TransferRequestSerializer(serializers.ModelSerializer):
    ticket_scan_url = serializers.SerializerMethodField()
    patient_id = serializers.SerializerMethodField()
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        required=False,
        allow_empty=True
    )

    class Meta:
        model = TransferRequest
        fields = [
            "id", "flight_number", "arrival_datetime",
            "ticket_scan", "ticket_scan_url", "tags", "created_at", "patient_id"
        ]
        read_only_fields = ["id", "created_at", "patient_id"]

    def get_ticket_scan_url(self, obj):
        request = self.context.get("request")
        if obj.ticket_scan and request:
            return request.build_absolute_uri(obj.ticket_scan.url)
        return None

    def get_patient_id(self, obj):
        patient = Patient.objects.filter(created_by=obj.user).first()
        return patient.id if patient else None

    def create(self, validated_data):
        user = self.context["request"].user
        tags_data = validated_data.pop('tags', None)

        transfer_request = TransferRequest.objects.create(user=user, **validated_data)

        if tags_data is None or len(tags_data) == 0:
            default_tag = Tag.objects.filter(code_name='new').first()
            if default_tag:
                transfer_request.tags.set([default_tag])
        else:
            transfer_request.tags.set(tags_data)

        return transfer_request

    def update(self, instance, validated_data):
        tags_data = validated_data.pop('tags', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tags_data is not None:
            instance.tags.set(tags_data)

        return instance


# ===============================================================
# 📱 SIM CARD REQUEST
# ===============================================================
class SimCardRequestSerializer(serializers.ModelSerializer):
    passport_scan_url = serializers.SerializerMethodField()
    patient_id = serializers.SerializerMethodField()
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        required=False,
        allow_empty=True
    )

    class Meta:
        model = SimCardRequest
        fields = [
            "id", "passport_scan", "passport_scan_url",
            "note", "tags", "created_at", "patient_id"
        ]
        read_only_fields = ["id", "created_at", "patient_id"]

    def get_passport_scan_url(self, obj):
        request = self.context.get("request")
        if obj.passport_scan and request:
            return request.build_absolute_uri(obj.passport_scan.url)
        return None

    def get_patient_id(self, obj):
        patient = Patient.objects.filter(created_by=obj.user).first()
        return patient.id if patient else None

    def create(self, validated_data):
        user = self.context["request"].user
        tags_data = validated_data.pop('tags', None)

        simcard_request = SimCardRequest.objects.create(user=user, **validated_data)

        if tags_data is None or len(tags_data) == 0:
            default_tag = Tag.objects.filter(code_name='new').first()
            if default_tag:
                simcard_request.tags.set([default_tag])
        else:
            simcard_request.tags.set(tags_data)

        return simcard_request

    def update(self, instance, validated_data):
        tags_data = validated_data.pop('tags', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tags_data is not None:
            instance.tags.set(tags_data)

        return instance


# ===============================================================
# 🏨 HOTEL LIST
# ===============================================================
class HotelSerializer(serializers.ModelSerializer):
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        required=False,
        allow_empty=True
    )

    class Meta:
        model = Hotel
        fields = ["id", "name", "address", "image", "stars", "price_per_night", "tags"]

    def create(self, validated_data):
        tags_data = validated_data.pop('tags', None)
        hotel = Hotel.objects.create(**validated_data)

        if tags_data is None or len(tags_data) == 0:
            default_tag = Tag.objects.filter(code_name='new').first()
            if default_tag:
                hotel.tags.set([default_tag])
        else:
            hotel.tags.set(tags_data)

        return hotel

    def update(self, instance, validated_data):
        tags_data = validated_data.pop('tags', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tags_data is not None:
            instance.tags.set(tags_data)

        return instance


class HotelImageSerializer(serializers.ModelSerializer):
    """Faqat image upload uchun serializer"""
    class Meta:
        model = Hotel
        fields = ["image"]


# ===============================================================
# 🛏️ BOOKING
# ===============================================================
class BookingSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="hotel.name", read_only=True)
    hotel_address = serializers.CharField(source="hotel.address", read_only=True)
    hotel_image = serializers.ImageField(source="hotel.image", read_only=True)
    patient_id = serializers.SerializerMethodField()
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        required=False,
        allow_empty=True
    )

    class Meta:
        model = Booking
        fields = [
            "id", "user", "hotel", "hotel_name", "hotel_address", "hotel_image",
            "start_date", "end_date", "guests", "tags", "created_at", "patient_id"
        ]
        read_only_fields = ["user", "created_at", "patient_id"]

    def get_patient_id(self, obj):
        patient = Patient.objects.filter(created_by=obj.user).first()
        return patient.id if patient else None

    def create(self, validated_data):
        user = self.context["request"].user
        tags_data = validated_data.pop('tags', None)

        booking = Booking.objects.create(user=user, **validated_data)

        if tags_data is None or len(tags_data) == 0:
            default_tag = Tag.objects.filter(code_name='new').first()
            if default_tag:
                booking.tags.set([default_tag])
        else:
            booking.tags.set(tags_data)

        return booking

    def update(self, instance, validated_data):
        tags_data = validated_data.pop('tags', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tags_data is not None:
            instance.tags.set(tags_data)

        return instance


# ===============================================================
# 🌐 TRANSLATOR REQUEST
# ===============================================================
class TranslatorRequestSerializer(serializers.ModelSerializer):
    patient_id = serializers.SerializerMethodField()
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        required=False,
        allow_empty=True
    )

    class Meta:
        model = TranslatorRequest
        fields = ["id", "language", "requirements", "tags", "created_at", "patient_id"]
        read_only_fields = ["id", "created_at", "patient_id"]

    def get_patient_id(self, obj):
        patient = Patient.objects.filter(created_by=obj.user).first()
        return patient.id if patient else None

    def create(self, validated_data):
        user = self.context["request"].user
        tags_data = validated_data.pop('tags', None)

        translator_request = TranslatorRequest.objects.create(user=user, **validated_data)

        if tags_data is None or len(tags_data) == 0:
            default_tag = Tag.objects.filter(code_name='new').first()
            if default_tag:
                translator_request.tags.set([default_tag])
        else:
            translator_request.tags.set(tags_data)

        return translator_request

    def update(self, instance, validated_data):
        tags_data = validated_data.pop('tags', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tags_data is not None:
            instance.tags.set(tags_data)

        return instance
