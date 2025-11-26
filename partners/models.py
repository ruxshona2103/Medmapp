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


# ===============================================================
# OPERATOR MODEL - MOVED TO authentication.models.OperatorProfile
# ===============================================================
# Operator modeli authentication app ichida mavjud.
# Agar operator profile kerak bo'lsa, authentication.models.OperatorProfile ishlatiladi.


# ===============================================================
# OPERATOR-PARTNER CONVERSATION MODEL
# ===============================================================
class OperatorPartnerConversation(models.Model):
    """
    Operator va Partner o'rtasidagi suhbat

    Bu model Operator va Partner o'rtasidagi suhbatlarni boshqarish uchun.
    Consultation modeliga o'xshash, lekin Operator-Partner uchun.
    """
    # Ishtirokchilar
    operator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='operator_partner_chats',
        verbose_name='Operator',
        limit_choices_to={'role': 'operator'}
    )

    partner = models.ForeignKey(
        Partner,
        on_delete=models.PROTECT,
        related_name='partner_operator_chats',
        verbose_name='Partner'
    )

    # Suhbat ma'lumotlari
    title = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Suhbat mavzusi'
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name='Faol'
    )

    # Kim yaratgan
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_op_partner_conversations',
        verbose_name='Yaratuvchi'
    )

    # Oxirgi xabar vaqti
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Oxirgi xabar vaqti'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Yaratilgan')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Yangilangan')

    class Meta:
        verbose_name = 'Operator-Partner Suhbat'
        verbose_name_plural = 'Operator-Partner Suhbatlar'
        db_table = 'partners_op_partner_conversation'
        ordering = ['-last_message_at', '-created_at']
        indexes = [
            models.Index(fields=['operator', 'is_active']),
            models.Index(fields=['partner', 'is_active']),
            models.Index(fields=['last_message_at']),
        ]
        # Bir operator va bir partner o'rtasida faqat bitta faol suhbat bo'lishi kerak
        constraints = [
            models.UniqueConstraint(
                fields=['operator', 'partner'],
                condition=models.Q(is_active=True),
                name='unique_active_op_partner_conversation'
            )
        ]

    def __str__(self):
        operator_name = getattr(self.operator, 'get_full_name', lambda: str(self.operator))()
        partner_name = self.partner.name
        return self.title or f"Suhbat: {operator_name} - {partner_name}"

    def save(self, *args, **kwargs):
        # Title bo'sh bo'lsa, avtomatik yaratish
        if not self.title:
            operator_name = getattr(self.operator, 'get_full_name', lambda: str(self.operator))()
            self.title = f"{operator_name} - {self.partner.name}"
        super().save(*args, **kwargs)


# ===============================================================
# OPERATOR-PARTNER MESSAGE MODEL
# ===============================================================
class OperatorPartnerMessage(models.Model):
    """
    Operator va Partner o'rtasidagi xabarlar
    """
    TYPE_CHOICES = (
        ('text', 'Matn'),
        ('file', 'Fayl'),
        ('system', 'Tizim xabari'),
    )

    # Suhbatga tegishli
    conversation = models.ForeignKey(
        OperatorPartnerConversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Suhbat'
    )

    # Kim yuborgan
    sender = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='op_partner_sent_messages',
        verbose_name='Yuboruvchi'
    )

    # Xabar turi va mazmuni
    type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        default='text',
        verbose_name='Xabar turi'
    )

    content = models.TextField(
        blank=True,
        null=True,
        verbose_name='Xabar matni'
    )

    # Javob berish
    reply_to = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='replies',
        verbose_name='Javob'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Yuborilgan')
    edited_at = models.DateTimeField(null=True, blank=True, verbose_name='Tahrirlangan')

    # Status
    is_deleted = models.BooleanField(default=False, verbose_name="O'chirilgan")
    is_read = models.BooleanField(default=False, verbose_name="O'qilgan")

    class Meta:
        verbose_name = 'Operator-Partner Xabar'
        verbose_name_plural = 'Operator-Partner Xabarlar'
        db_table = 'partners_op_partner_message'
        ordering = ['created_at', 'id']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['conversation', 'is_read']),
        ]

    def __str__(self):
        return f"Xabar #{self.pk} - {self.conversation}"

    def soft_delete(self):
        """Xabarni soft delete qilish"""
        self.is_deleted = True
        self.content = "[O'chirilgan xabar]"
        self.save(update_fields=['is_deleted', 'content'])

    def mark_as_read(self):
        """Xabarni o'qilgan deb belgilash"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])


# ===============================================================
# OPERATOR-PARTNER ATTACHMENT MODEL
# ===============================================================
def op_partner_chat_upload_path(instance, filename):
    """
    Fayl yuklash yo'li
    """
    import os
    timestamp = timezone.now()
    safe_filename = "".join(
        c for c in os.path.basename(filename) if c.isalnum() or c in "._-"
    )
    return f"op_partner_chat/{timestamp:%Y/%m/%d}/{instance.message_id}_{safe_filename}"


class OperatorPartnerAttachment(models.Model):
    """
    Operator-Partner xabariga biriktirilgan fayl
    """
    FILE_TYPE_CHOICES = (
        ('image', 'Rasm'),
        ('video', 'Video'),
        ('document', 'Hujjat'),
        ('other', 'Boshqa'),
    )

    # Xabarga tegishli
    message = models.ForeignKey(
        OperatorPartnerMessage,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='Xabar'
    )

    # Fayl ma'lumotlari
    file = models.FileField(
        upload_to=op_partner_chat_upload_path,
        verbose_name='Fayl'
    )

    file_type = models.CharField(
        max_length=20,
        choices=FILE_TYPE_CHOICES,
        default='other',
        verbose_name='Fayl turi'
    )

    mime_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='MIME turi'
    )

    size = models.PositiveBigIntegerField(
        default=0,
        verbose_name='Hajm (bytes)'
    )

    original_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Asl fayl nomi'
    )

    # Kim yuklagan
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='op_partner_chat_files',
        verbose_name='Yuklagan'
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Yuklangan vaqt'
    )

    class Meta:
        verbose_name = 'Operator-Partner Fayl'
        verbose_name_plural = 'Operator-Partner Fayllar'
        db_table = 'partners_op_partner_attachment'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['message', 'uploaded_at']),
            models.Index(fields=['uploaded_by']),
        ]

    def save(self, *args, **kwargs):
        """Fayl ma'lumotlarini avtomatik to'ldirish"""
        import os
        import mimetypes

        if self.file:
            # Fayl nomini saqlash
            self.original_name = (
                os.path.basename(self.file.name) if hasattr(self.file, 'name') else ''
            )

            # Hajmni saqlash
            if hasattr(self.file, 'size'):
                self.size = self.file.size

            # MIME turi
            if hasattr(self.file, 'content_type') and self.file.content_type:
                self.mime_type = self.file.content_type
            elif self.original_name:
                guessed, _ = mimetypes.guess_type(self.original_name)
                self.mime_type = guessed or 'application/octet-stream'
            else:
                self.mime_type = self.mime_type or 'application/octet-stream'

            # Fayl turini aniqlash
            if self.mime_type.startswith('image/'):
                self.file_type = 'image'
            elif self.mime_type.startswith('video/'):
                self.file_type = 'video'
            elif self.mime_type.startswith(
                ('application/pdf', 'application/msword',
                 'application/vnd.openxmlformats-officedocument')
            ):
                self.file_type = 'document'
            else:
                self.file_type = 'other'

        super().save(*args, **kwargs)

    def get_file_url(self):
        """Fayl URL"""
        return self.file.url if self.file else None

    @property
    def formatted_size(self):
        """Formatlangan hajm"""
        size = self.size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def __str__(self):
        return f"{self.original_name} - {self.formatted_size}"
