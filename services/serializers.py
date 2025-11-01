from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from patients.models import Patient
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

    class Meta:
        model = VisaRequest
        fields = [
            "id", "passport_scan", "passport_scan_url",
            "note", "created_at", "patient_id"
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
        return VisaRequest.objects.create(user=user, **validated_data)


# ===============================================================
# ✈️ TRANSFER REQUEST
# ===============================================================
class TransferRequestSerializer(serializers.ModelSerializer):
    ticket_scan_url = serializers.SerializerMethodField()
    patient_id = serializers.SerializerMethodField()

    class Meta:
        model = TransferRequest
        fields = [
            "id", "flight_number", "arrival_datetime",
            "ticket_scan", "ticket_scan_url", "created_at", "patient_id"
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
        return TransferRequest.objects.create(user=user, **validated_data)


# ===============================================================
# 📱 SIM CARD REQUEST
# ===============================================================
class SimCardRequestSerializer(serializers.ModelSerializer):
    passport_scan_url = serializers.SerializerMethodField()
    patient_id = serializers.SerializerMethodField()

    class Meta:
        model = SimCardRequest
        fields = [
            "id", "passport_scan", "passport_scan_url",
            "note", "created_at", "patient_id"
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
        return SimCardRequest.objects.create(user=user, **validated_data)


# ===============================================================
# 🏨 HOTEL LIST
# ===============================================================
class HotelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        fields = ["id", "name", "address", "image", "stars", "price_per_night"]


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

    class Meta:
        model = Booking
        fields = [
            "id", "user", "hotel", "hotel_name", "hotel_address", "hotel_image",
            "start_date", "end_date", "guests", "created_at", "patient_id"
        ]
        read_only_fields = ["user", "created_at", "patient_id"]

    def get_patient_id(self, obj):
        patient = Patient.objects.filter(created_by=obj.user).first()
        return patient.id if patient else None

    def create(self, validated_data):
        user = self.context["request"].user
        return Booking.objects.create(user=user, **validated_data)


# ===============================================================
# 🌐 TRANSLATOR REQUEST
# ===============================================================
class TranslatorRequestSerializer(serializers.ModelSerializer):
    patient_id = serializers.SerializerMethodField()

    class Meta:
        model = TranslatorRequest
        fields = ["id", "language", "requirements", "created_at", "patient_id"]
        read_only_fields = ["id", "created_at", "patient_id"]

    def get_patient_id(self, obj):
        patient = Patient.objects.filter(created_by=obj.user).first()
        return patient.id if patient else None

    def create(self, validated_data):
        user = self.context["request"].user
        return TranslatorRequest.objects.create(user=user, **validated_data)
