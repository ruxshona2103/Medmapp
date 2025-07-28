from rest_framework import serializers
from .models import Departments


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Departments
        fields = [
            'id',
            'name', 'name_uz', 'name_ru', 'name_en',
            'description', 'description_uz', 'description_ru', 'description_en',
            'icon'
        ]