from django.db import models
from django.conf import settings
from django.utils import timezone
from .validators import validate_future_dt, validate_file_type, validate_future_date_range

User = settings.AUTH_USER_MODEL

class TimeStampedModel(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    isAccepted = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Automatically set isAccepted based on status
        if self.status == 'pending':
            self.isAccepted = False
        elif self.status == 'accepted':
            self.isAccepted = True
        super().save(*args, **kwargs)

class VisaRequest(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="viza_sorovlari")
    passport_scan = models.FileField(upload_to="visa/passports/", validators=[validate_file_type])
    note = models.CharField(max_length=500, blank=True)

class TransferRequest(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="transfer_sorovlari")
    flight_number = models.CharField(max_length=50)
    arrival_datetime = models.DateTimeField(validators=[validate_future_dt])
    ticket_scan = models.FileField(upload_to="transfer/tickets/", blank=True, null=True, validators=[validate_file_type])

class TranslatorRequest(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tarjimon_sorovlari")
    language = models.CharField(max_length=50)
    requirements = models.TextField(blank=True)

class SimCardRequest(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="simkarta_sorovlari")
    passport_scan = models.FileField(upload_to="simcard/passports/", validators=[validate_file_type])
    note = models.CharField(max_length=500, blank=True)

class Booking(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="bookingd")
    start_date = models.DateField()
    end_date = models.DateField()
    guests = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.user} → {self.hotel.name} ({self.start_date} - {self.end_date})"