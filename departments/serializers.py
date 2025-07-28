from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from departments.models import Departments


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Departments
        fields = [
            'id',
            'name', 'name_uz', 'name_ru', 'name_en',
            'description', 'description_uz', 'description_ru', 'description_en',
            'icon'
        ]



class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        # tokenlarni string qilib qo‘shamiz
        data['access'] = str(data.get('access'))
        data['refresh'] = str(data.get('refresh'))

        return data

