from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters
from .models import Departments
from .serializers import DepartmentSerializer

class DepartmentsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Departments.objects.all()
    serializer_class = DepartmentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['name']
    search_fields = ['name', 'description']
