from django.db import models

class Stage(models.Model):
    """
    Kanban ustunlari (TZ 2.2, 3.3).
    'response_letters' kabi maxsus saralashlar uchun code_name ham kerak bo‘ladi (TZ 3.5).
    """
    title = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=32, default="#999999")
    # TZ 3.5 da filterda 'response_letters' ishlatiladi → code_name ni qo‘shamiz
    code_name = models.CharField(max_length=64, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"{self.order}. {self.title}"


class Tag(models.Model):
    """
    Bemorlarni kategoriyalash (TZ 2.3, 3.2).
    """
    name = models.CharField(max_length=64, unique=True)
    color = models.CharField(max_length=32, default="default")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name
