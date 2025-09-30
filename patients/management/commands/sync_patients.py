from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from applications.models import Application
from patients.models import Patient, PatientProfile, Stage

User = get_user_model()


class Command(BaseCommand):
    help = "Applications asosida PatientProfile va Patientlarni sync qilish"

    def handle(self, *args, **kwargs):
        applications = Application.objects.select_related("patient").all()
        created_profiles = 0
        created_patients = 0

        for app in applications:
            user = app.patient  # Application dagi patient = User
            self.stdout.write(
                f"Processing Application {app.id} -> User {user.id} ({user.phone_number})"
            )

            # 1️⃣ PatientProfile yaratish yoki olish
            profile, profile_created = PatientProfile.objects.get_or_create(
                user=user,
                defaults={
                    "full_name": user.get_full_name()
                    or user.phone_number
                    or "Noma'lum",
                    "gender": "male",  # default
                    "complaints": app.complaint or "",
                    "previous_diagnosis": app.diagnosis or "",
                },
            )
            if profile_created:
                created_profiles += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"PatientProfile yaratildi: {profile.full_name} (User {user.id})"
                    )
                )

            # 2️⃣ Stage (status) tekshirish
            stage = Stage.objects.filter(code_name=app.status).first()
            if not stage:
                stage, _ = Stage.objects.get_or_create(
                    code_name="new",
                    defaults={"title": "Yangi", "order": 0},
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"No stage for status {app.status}, default 'new' ishlatildi"
                    )
                )

            # 3️⃣ Patient yaratish yoki yangilash (har Application uchun alohida!)
            patient, patient_created = Patient.objects.update_or_create(
                profile=profile,
                source=f"Application_{app.id}",  # 🔑 Application ID unique bo‘ladi
                defaults={
                    "full_name": profile.full_name,
                    "phone": user.phone_number,
                    "email": getattr(user, "email", None),
                    "stage": stage,
                    "created_by": user,
                },
            )

            if patient_created:
                created_patients += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Patient yaratildi: {patient.full_name} (Application {app.id})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Patient yangilandi: {patient.full_name} (Application {app.id})"
                    )
                )

        # ✅ Yakuniy natija
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_profiles} PatientProfile(s) va {created_patients} Patient(s)"
            )
        )
