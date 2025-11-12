# patients/apps.py
from django.apps import AppConfig

class PatientsConfig(AppConfig):
    name = "patients"
    verbose_name = "Patients"

    def ready(self):
        # signals ni shu yerda import qilamiz
        import patients.signals  # noqa: F401
