from django.db import models

class Departments(models.Model):
    name = models.CharField(max_length=255, null=False, blank=False)
    description = models.TextField()
    icon = models.ImageField(upload_to='department_icons', null=True, blank=True)

    def __str__(self):
        return self.name

