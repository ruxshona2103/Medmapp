# partners/models.py
# ===============================================================
# HAMKOR PANEL - MODELS (TO'LIQ TO'G'RILANGAN)
# ===============================================================

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


# ===============================================================
# PARTNER MODEL
# ===============================================================
class Partner(models.Model):
    """
    Hamkor (Klinika/Shifokor) profili
    """

    # User relation
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='partner_profile',
        verbose_name='Foydalanuvchi'
    )

    # Hamkor ma'lumotlari
    name = models.CharField(
        max_length=255,
        verbose_name='Klinika/Shifokor nomi',
        help_text='Masalan: "Medion Klinika" yoki "Dr. Aliyev"'
    )

    avatar = models.ImageField(
        upload_to='partner_avatars/',
        blank=True,
        null=True,
        verbose_name='Profil rasmi'
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Hamkor kodi',
        help_text='Masalan: "MEDION_01"'
    )

    specialization = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Mutaxassislik',
        help_text='Masalan: "Kardiologiya", "Nevrologiya"'
    )

    # Contact
    contact_person = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Mas\'ul shaxs',
        help_text='Aloqa uchun mas\'ul shaxs ismi'
    )

    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Telefon'
    )

    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name='Email'
    )

    # Telegram notification
    telegram_chat_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Telegram Chat ID',
        help_text='Yangi bemorlar haqida xabarnoma uchun Telegram guruh ID'
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name='Faol',
        help_text='Hamkor faolmi?'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Yaratilgan vaqt')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='O\'zgartirilgan vaqt')

    class Meta:
        verbose_name = 'Hamkor'
        verbose_name_plural = 'Hamkorlar'
        ordering = ['-created_at']
        db_table = 'partners_partner'

    def __str__(self):
        return f"{self.name} ({self.code})"

    # ===============================================================
    # PROPERTIES - TO'G'RILANGAN
    # ===============================================================

    @property
    def total_patients(self):
        """Jami bemorlar soni"""
        return self.assigned_patients.count()

    @property
    def active_patients(self):
        """
        Faol bemorlar soni (HUJJATLAR, JAVOB_XATLARI bosqichlarida)

        ✅ TO'G'RI VERSIYA - stage__in ishlatish
        """
        try:
            from core.models import Stage

            # Stage ID larini olish
            active_stage_ids = Stage.objects.filter(
                code__in=['stage_documents', 'stage_response']
            ).values_list('id', flat=True)

            # Bemorlarni filter qilish (stage_id__in)
            return self.assigned_patients.filter(
                stage_id__in=active_stage_ids
            ).count()

        except Exception:
            # Agar xato bo'lsa, 0 qaytarish
            return 0


# ===============================================================
# PARTNER RESPONSE DOCUMENT MODEL
# ===============================================================
class PartnerResponseDocument(models.Model):
    """
    Hamkor javob xati (Tibbiy xulosa, narxlar, tavsiyalar)
    """

    # Relations
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='partner_responses',
        verbose_name='Bemor'
    )

    partner = models.ForeignKey(
        Partner,
        on_delete=models.CASCADE,
        related_name='uploaded_responses',
        verbose_name='Hamkor'
    )

    # File
    file = models.FileField(
        upload_to='partner_responses/%Y/%m/%d/',
        verbose_name='Fayl',
        help_text='Tibbiy xulosa, narxlar jadvali PDF/DOC'
    )

    file_name = models.CharField(
        max_length=255,
        verbose_name='Fayl nomi'
    )

    # Description
    title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Sarlavha',
        help_text='Masalan: "Tibbiy xulosa", "Narxlar jadvali"'
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='Izoh',
        help_text='Qo\'shimcha ma\'lumot'
    )

    # Document type
    DOCUMENT_TYPES = [
        ('medical_report', 'Tibbiy xulosa'),
        ('price_list', 'Narxlar jadvali'),
        ('recommendations', 'Tavsiyalar'),
        ('other', 'Boshqa'),
    ]

    document_type = models.CharField(
        max_length=50,
        choices=DOCUMENT_TYPES,
        default='medical_report',
        verbose_name='Hujjat turi'
    )

    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Yuklangan vaqt')

    class Meta:
        verbose_name = 'Hamkor javob xati'
        verbose_name_plural = 'Hamkor javob xatlari'
        ordering = ['-uploaded_at']
        db_table = 'partners_response_document'

    def __str__(self):
        return f"{self.partner.name} - {self.patient.full_name} - {self.file_name}"

    def save(self, *args, **kwargs):
        """File nomini avtomatik saqlash"""
        if self.file and not self.file_name:
            self.file_name = self.file.name.split('/')[-1]
        super().save(*args, **kwargs)
