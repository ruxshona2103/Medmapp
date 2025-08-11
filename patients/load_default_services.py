from django.core.management.base import BaseCommand
from patients.models import Service


class Command(BaseCommand):
    help = 'Load initial services into DB'

    def handle(self, *args, **options):
        services = [
            {
                'service_id': 'invitation',
                'name': 'Taklifnoma (Invitation)',
                'description': 'Rasmiy taklifnoma',
                'price': '0.00',
                'price_description': 'Taklifnoma bepul',
                'icon_class': 'bi-envelope'
            },
            {
                'service_id': 'visa_support',
                'name': 'Viza yordami',
                'description': 'Viza uchun hujjat tayyorlash',
                'price': '100.00',
                'price_description': 'Viza $100',
                'icon_class': 'bi-pass'
            },
        ]
        for s in services:
            obj, created = Service.objects.update_or_create(service_id=s['service_id'], defaults=s)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created {obj.service_id}"))
            else:
                self.stdout.write(self.style.WARNING(f"Updated {obj.service_id}"))