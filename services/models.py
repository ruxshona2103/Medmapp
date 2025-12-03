from django.conf import settings
from django.db import models
from .validators import validate_future_dt, validate_file_type, validate_future_date_range

User = settings.AUTH_USER_MODEL

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Hotel(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to="hotels/", null=True, blank=True)
    stars = models.PositiveSmallIntegerField(default=3)
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    tags = models.ManyToManyField('core.Tag', blank=True, related_name='hotels')

    def __str__(self):
        return self.name


class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="bookingd")
    start_date = models.DateField()
    end_date = models.DateField()
    guests = models.PositiveIntegerField()
    created_at = models.DateField(auto_now_add=True)
    tags = models.ManyToManyField('core.Tag', blank=True, related_name='bookings')

    def __str__(self):
        return f"{self.user} → {self.hotel.name} ({self.start_date} - {self.end_date})"


class VisaRequest(TimeStampedModel):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="viza_sorovlari")
    passport_scan = models.FileField( upload_to="visa/passports/", validators=[validate_file_type])
    note = models.CharField(max_length=500, blank=True)
    tags = models.ManyToManyField('core.Tag', blank=True, related_name='visa_requests')


class TransferRequest(TimeStampedModel):
    user = models.ForeignKey(User,on_delete=models.CASCADE, related_name="transfer_sorovlari")
    flight_number = models.CharField(max_length=50)
    arrival_datetime = models.DateTimeField(validators=[validate_future_dt])
    ticket_scan = models.FileField(upload_to="transfer/tickets/",blank=True,null=True,validators=[validate_file_type])
    tags = models.ManyToManyField('core.Tag', blank=True, related_name='transfer_requests')


class TranslatorRequest(TimeStampedModel):
    user = models.ForeignKey( User,on_delete=models.CASCADE,related_name="tarjimon_sorovlari")
    language = models.CharField(max_length=50)
    requirements = models.TextField(blank=True)
    tags = models.ManyToManyField('core.Tag', blank=True, related_name='translator_requests')


class SimCardRequest(TimeStampedModel):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="simkarta_sorovlari")
    passport_scan = models.FileField(upload_to="simcard/passports/",validators=[validate_file_type])
    note = models.CharField(max_length=500, blank=True)
    tags = models.ManyToManyField('core.Tag', blank=True, related_name='simcard_requests')
