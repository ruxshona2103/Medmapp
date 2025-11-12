from django.apps import AppConfig

class PartnersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "partners"

    def ready(self):
        from . import signals  # noqa
