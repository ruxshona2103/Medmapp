from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PartnerPatientViewSet,PartnerProfileView

router = DefaultRouter()
router.register(r'patients', PartnerPatientViewSet, basename='partner-patients')

urlpatterns = [
    path('', include(router.urls)),
    path('profile/', PartnerProfileView.as_view(), name='partner-profile'),
]
