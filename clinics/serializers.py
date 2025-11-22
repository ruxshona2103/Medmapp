# clinics/serializers.py
from rest_framework import serializers
from .models import (
    Country, City, Accreditation, Specialty, Clinic, ClinicSpecialty,
    Doctor, TreatmentPrice, ClinicInfrastructure, ClinicImage, NearbyStay,
    WorldClinic
)

# === Small helpers ===
def tr(obj, base: str):
    """Return dict with all languages: {'uz':..., 'ru':..., 'en':...}"""
    return {
        "uz": getattr(obj, f"{base}_uz", None),
        "ru": getattr(obj, f"{base}_ru", None),
        "en": getattr(obj, f"{base}_en", None),
    }

class CountrySerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    class Meta:
        model = Country
        fields = ["id", "code", "title"]
    def get_title(self, obj): return tr(obj, "title")

class CitySerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    country = CountrySerializer(read_only=True)
    class Meta:
        model = City
        fields = ["id", "title", "country"]
    def get_title(self, obj): return tr(obj, "title")

class AccreditationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accreditation
        fields = ["code", "name"]


# === Specialty ===
class SpecialtySerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    icon_url = serializers.SerializerMethodField()
    class Meta:
        model = Specialty
        fields = ["id", "title", "description", "icon_url", "is_active"]
    def get_title(self, o): return tr(o, "title")
    def get_description(self, o): return tr(o, "description")
    def get_icon_url(self, o):
        try:
            if o.icon:
                r = self.context.get("request")
                if r:
                    return r.build_absolute_uri(o.icon.url)
                return o.icon.url
        except:
            pass
        return None


# === Doctors & Prices ===
class DoctorSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    specialty = SpecialtySerializer(read_only=True)
    class Meta:
        model = Doctor
        fields = ["id", "full_name", "title", "photo_url", "specialty",
                  "experience_years", "work_time", "is_top", "order"]
    def get_title(self, o): return {"uz": o.title_uz, "ru": o.title_ru, "en": o.title_en}
    def get_photo_url(self, o):
        try:
            if o.photo:
                r = self.context.get("request")
                if r:
                    return r.build_absolute_uri(o.photo.url)
                return o.photo.url
        except:
            pass
        return None

class TreatmentPriceSerializer(serializers.ModelSerializer):
    procedure = serializers.SerializerMethodField()
    specialty = SpecialtySerializer(read_only=True)
    class Meta:
        model = TreatmentPrice
        fields = ["id", "procedure", "price_usd", "order", "is_active", "specialty"]
    def get_procedure(self, o):
        return {"uz": o.procedure_uz, "ru": o.procedure_ru, "en": o.procedure_en}


# === Infra / Gallery / Nearby ===
class ClinicInfrastructureSerializer(serializers.ModelSerializer):
    text = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    class Meta:
        model = ClinicInfrastructure
        fields = ["id", "text", "image_url", "order"]
    def get_text(self, o): return {"uz": o.text_uz, "ru": o.text_ru, "en": o.text_en}
    def get_image_url(self, o):
        try:
            if o.image:
                r = self.context.get("request")
                if r:
                    return r.build_absolute_uri(o.image.url)
                return o.image.url
        except:
            pass
        return None

class ClinicImageSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    class Meta:
        model = ClinicImage
        fields = ["id", "image_url", "title", "description", "order"]
    def get_title(self, o): return tr(o, "title")
    def get_description(self, o): return tr(o, "description")
    def get_image_url(self, o):
        try:
            if o.image:
                r = self.context.get("request")
                if r:
                    return r.build_absolute_uri(o.image.url)
                return o.image.url
        except:
            pass
        return None

class NearbyStaySerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    class Meta:
        model = NearbyStay
        fields = ["id", "title", "description", "address", "rating", "image_url"]
    def get_title(self, o): return tr(o, "title")
    def get_description(self, o): return tr(o, "description")
    def get_image_url(self, o):
        try:
            if o.image:
                r = self.context.get("request")
                if r:
                    return r.build_absolute_uri(o.image.url)
                return o.image.url
        except:
            pass
        return None


# === Clinic cards & details ===
class ClinicCardSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    city = CitySerializer(read_only=True)
    country = CountrySerializer(read_only=True)
    cover_url = serializers.SerializerMethodField()
    accreditations = AccreditationSerializer(many=True, read_only=True)
    specialties = SpecialtySerializer(many=True, read_only=True)

    class Meta:
        model = Clinic
        fields = [
            "id", "slug", "title", "address", "city", "country",
            "cover_url", "rating", "accreditations", "specialties",
        ]

    def get_title(self, o): return tr(o, "title")
    def get_address(self, o):
        return {"uz": o.address_uz, "ru": o.address_ru, "en": o.address_en}
    def get_cover_url(self, o):
        try:
            if o.cover_image:
                r = self.context.get("request")
                if r:
                    return r.build_absolute_uri(o.cover_image.url)
                return o.cover_image.url
        except:
            pass
        return None


class ClinicDetailSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    city = CitySerializer(read_only=True)
    country = CountrySerializer(read_only=True)
    background_url = serializers.SerializerMethodField()
    accreditations = AccreditationSerializer(many=True, read_only=True)
    specialties = SpecialtySerializer(many=True, read_only=True)

    # nested short blocks
    top_doctors = serializers.SerializerMethodField()
    top_prices = serializers.SerializerMethodField()

    class Meta:
        model = Clinic
        fields = [
            "id", "slug", "title", "description", "address",
            "city", "country",
            "background_url", "rating", "founded_year",
            "bed_count", "department_count", "operating_room_count",
            "accreditations", "specialties",
            "top_doctors", "top_prices",
        ]

    def get_title(self, o): return tr(o, "title")
    def get_description(self, o): return tr(o, "description")
    def get_address(self, o):
        return {"uz": o.address_uz, "ru": o.address_ru, "en": o.address_en}
    def get_background_url(self, o):
        try:
            if o.background_image:
                r = self.context.get("request")
                if r:
                    return r.build_absolute_uri(o.background_image.url)
                return o.background_image.url
        except:
            pass
        return None

    def get_top_doctors(self, o):
        qs = o.doctors.filter(is_top=True).order_by("order")[:3]
        return DoctorSerializer(qs, many=True, context=self.context).data

    def get_top_prices(self, o):
        qs = o.prices.filter(is_active=True).order_by("order")[:6]
        return TreatmentPriceSerializer(qs, many=True, context=self.context).data


# === Jahon Klinikalari ===
class WorldClinicSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    country = CountrySerializer(read_only=True)

    class Meta:
        model = WorldClinic
        fields = ["id", "title", "description", "image_url", "famous_doctors_count", "country", "is_active"]

    def get_title(self, o): return tr(o, "title")
    def get_description(self, o): return tr(o, "description")
    def get_image_url(self, o):
        try:
            if o.image:
                r = self.context.get("request")
                if r:
                    return r.build_absolute_uri(o.image.url)
                return o.image.url
        except:
            pass
        return None
