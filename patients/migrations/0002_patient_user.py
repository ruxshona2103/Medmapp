# patients/migrations/0002_patient_user.py
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),  # auth user model talab
    ]

    operations = [
        migrations.AddField(
            model_name='patient',
            name='user',
            field=models.OneToOneField(
                related_name='patient_profile',
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
                null=True,      # ⚠️ 1-bosqich: vaqtincha nullable
                blank=True,
            ),
        ),
    ]
