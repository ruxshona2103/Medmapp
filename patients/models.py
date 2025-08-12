from django.conf import settings
from django.db import models


class PatientProfile(models.Model):
    GENDER_CHOICES = (
        ("Erkak", "Erkak"),
        ("Ayol", "Ayol"),
    )
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='patient_profile')
    fullName = models.CharField(max_length=255)
    passport = models.CharField(max_length=20)
    dob = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    phone = models.CharField(max_length=20)
    email = models.CharField(max_length=30)

    def __str__(self):
        return f"{self.fullName} ({self.user.username})"

class Application(models.Model):
    STATUS_CHOICES = (
        ("new", "new"),
        ("processing", "processing"),
        ("completed", "completed"),
    )
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='applications')
    complaint = models.TextField()
    diagnosis = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, default='new', choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Application #{self.id} - {self.patient.username} - {self.status}"

class Document(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Document {self.id} for App {self.application.id}"

class Service(models.Model):
    service_id = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    price_description = models.CharField(max_length=255)
    icon_class = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.name} ({self.service_id})"

class OrderedService(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='ordered_services')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='orders')
    order_date = models.DateTimeField(auto_now_add=True)
    data = models.JSONField(null=True, blank=True)
    current_status_index = models.IntegerField(default=0)

    def __str__(self):
        return f"OrderedService {self.id} - {self.service.name} for App {self.application.id}"

class ServiceStatusHistory(models.Model):
    ordered_service = models.ForeignKey(OrderedService, on_delete=models.CASCADE, related_name='status_history')
    status_text = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Status {self.status_text} at {self.date}"
