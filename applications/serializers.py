
from rest_framework import serializers
from .models import Application, Document, ApplicationHistory
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'phone_number', 'first_name', 'last_name']

class ApplicationHistorySerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = ApplicationHistory
        fields = ['id', 'author', 'comment', 'created_at']
class DocumentSerializer(serializers.ModelSerializer):
    # --- TO'G'RILANDI: `application` maydoni `read_only` qilindi ---
    # Bu Swagger'dagi chalkashlikning oldini oladi.
    # `application` endi View tomonidan avtomatik to'ldiriladi.
    class Meta:
        model = Document
        fields = ["id", "application", "file", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at", "application"]

class ApplicationSerializer(serializers.ModelSerializer):
    patient = UserSerializer(read_only=True)
    history = ApplicationHistorySerializer(many=True, read_only=True)

    # --- TO'G'RILANDI: Samaradorlik muammosi hal qilindi (N+1 Query) ---
    # `patient` (User) bilan bog'liq `Patient` modelining ID'sini to'g'ridan-to'g'ri olamiz.
    # Bu alohida DB so'rov yubormaydi, agar view'da prefetch qilingan bo'lsa.
    # Agar patient_record mavjud bo'lmasa, xatolik bermaslik uchun `allow_null=True`.
    patient_record_id = serializers.IntegerField(source='patient.patient_profile.patient_records.first.id', read_only=True, allow_null=True)
    documents = DocumentSerializer(many=True, read_only=True)
    class Meta:
        model = Application
        fields = [
            "id",
            "application_id",
            "patient",
            "patient_record_id", # Yangilangan maydon nomi
            "linked_patient",
            "clinic_name",
            "complaint",
            "diagnosis",
            "created_at",
            "updated_at",
             "stage",
             "documents",
            "history",
        ]
        read_only_fields = [
            "application_id",
            "created_at",
            "updated_at",
            "patient",
            "stage",
            "documents",
            "patient_record_id", # Yangilangan maydon nomi
            "linked_patient",
            "history",
        ]

    # --- O'CHIRILDI: Bu keraksiz `create` metodi olib tashlandi ---
    # View'dagi `perform_create` bu vazifani bajaradi.


