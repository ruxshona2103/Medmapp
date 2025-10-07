from django.apps import AppConfig

class PatientsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "patients"

    def ready(self):
        from . import signals  # noqa: F401
