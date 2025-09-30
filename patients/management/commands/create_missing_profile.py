# patients/management/commands/create_missing_profiles.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from patients.models import PatientProfile
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Create PatientProfile for users without one"

    def handle(self, *args, **options):
        users_without_profile = User.objects.filter(patient_profile__isnull=True, role="user")
        created_count = 0

        for user in users_without_profile:
            profile, created = PatientProfile.objects.get_or_create(
                user=user,
                defaults={
                    "full_name": user.get_full_name() or user.phone_number or "Noma'lum",
                    "gender": "male",
                    "complaints": "",
                    "previous_diagnosis": "",
                }
            )
            if created:
                logger.info(f"Created PatientProfile for User {user.id} ({user.phone_number})")
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created_count} PatientProfile(s)"))