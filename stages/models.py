from django.db import models

class Stage(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Bosqich nomi")
    color = models.CharField(max_length=20, default="primary", help_text="Masalan: primary, success, danger yoki #FF5733", verbose_name="Rang")
    order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="Tartib raqami")
    code_name = models.CharField(max_length=50, unique=True, verbose_name="Kod nomi (dasturchi uchun)", blank=True, null=True)
    class Meta:
        ordering = ['order']
        verbose_name = "Bosqich"
        verbose_name_plural = "Bosqichlar"

    def __str__(self):
        return self.name