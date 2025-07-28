from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters
from .models import Departments
from .serializers import DepartmentSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer


class DepartmentsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Departments.objects.all()
    serializer_class = DepartmentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['name']
    search_fields = ['name', 'description']



class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        # agar status_code 200 bo‘lsa, user haqida ma’lumot qo‘shamiz
        if response.status_code == 200:
            user = self.get_user(request.data.get('username'))
            response.data['user'] = {
                'username': user.username,
                'is_superuser': user.is_superuser
            }
        return response

    def get_user(self, username):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.get(username=username)
