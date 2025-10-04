from django.db import models

class Stage(models.Model):
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=20)
    order = models.PositiveIntegerField(default=0)
    code_name = models.CharField(max_length=50, unique=True, default="default_code")

    def save(self, *args, **kwargs):
        # Agar order kiritilmagan bo‘lsa, avtomatik tartib raqam beradi
        if not self.order:
            last_stage = Stage.objects.order_by('-order').first()
            self.order = (last_stage.order + 1) if last_stage else 1

        # Agar code_name hali bo‘lmasa, avtomatik yaratiladi
        if not self.code_name or self.code_name == "default_code":
            self.code_name = f"stage_{self.order}"

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} (order={self.order})"
