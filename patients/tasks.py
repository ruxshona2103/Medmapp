from celery import shared_task
from django.conf import settings
from .models import Patient
import requests


@shared_task
def send_new_patient_notification(patient_id: int):
    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return

    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None)
    if not token or not chat_id:
        return

    text = (
        f"🆕 Yangi bemor qo‘shildi:\n"
        f"👤 {patient.full_name}\n"
        f"📞 {patient.phone_number}\n"
        f"📦 Manba: {patient.source or '-'}"
    )
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": text})
