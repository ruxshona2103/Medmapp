from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import (
    VisaRequest,
    TransferRequest,
    TranslatorRequest,
    SimCardRequest,
    Hotel,
    Booking,
)

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


class VisaRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisaRequest
        fields = ["id", "passport_scan", "note", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        return VisaRequest.objects.create(user=self.context["request"].user, **validated_data)


class TransferRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferRequest
        fields = ["id", "flight_number", "arrival_datetime", "ticket_scan", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        return TransferRequest.objects.create(user=self.context["request"].user, **validated_data)




class HotelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        fields = ["id", "name", "address", "image", "stars", "price_per_night"]


class HotelImageSerializer(serializers.ModelSerializer):
    """Faqat image upload uchun serializer"""
    class Meta:
        model = Hotel
        fields = ["image"]



class BookingSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="hotel.name", read_only=True)
    hotel_address = serializers.CharField(source="hotel.address", read_only=True)
    hotel_image = serializers.ImageField(source="hotel.image", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "user", "hotel", "hotel_name", "hotel_address", "hotel_image",
            "start_date", "end_date", "guests", "created_at"
        ]
        read_only_fields = ["user", "created_at"]

class TranslatorRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = TranslatorRequest
        fields = ["id", "language", "requirements", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        return TranslatorRequest.objects.create(user=self.context["request"].user, **validated_data)


class SimCardRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SimCardRequest
        fields = ["id", "passport_scan", "note", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        return SimCardRequest.objects.create(user=self.context["request"].user, **validated_data)
