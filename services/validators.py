import mimetypes
from django.core.exceptions import ValidationError
from django.utils import timezone

ALLOWED_MIME = {"application/pdf", "image/jpeg", "image/png"}


def validate_file_type(fobj):
    """
    Fayl turini tekshiradi: faqat PDF, JPG, PNG.
    """
    ctype, _ = mimetypes.guess_type(fobj.name)
    if ctype not in ALLOWED_MIME:
        raise ValidationError("Faqat PDF, JPG va PNG fayllar yuklash mumkin.")


def validate_future_dt(value):
    if value <= timezone.now():
        raise ValidationError("Sana va vaqt kelajakda bo‘lishi shart.")


def validate_future_date_range(start_date, end_date):
    """
    Sana oralig‘ini tekshiradi:
    - check_in kelajakda bo‘lishi kerak
    - check_out check_in dan keyin bo‘lishi kerak
    """
    today = timezone.localdate()
    if start_date is None or end_date is None:
        raise ValidationError("Ikkala sana ham kiritilishi shart.")
    if start_date <= today:
        raise ValidationError({"check_in": "check_in kelajakda bo‘lishi kerak."})
    if end_date <= start_date:
        raise ValidationError({"check_out": "check_out check_in dan keyin bo‘lishi kerak."})
