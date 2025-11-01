from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PartnerPatientViewSet,
    PartnerProfileView,
    PartnerResponseViewSet,
)

router = DefaultRouter()
router.register(r'patients', PartnerPatientViewSet, basename='partner-patients')
router.register(r'responses', PartnerResponseViewSet, basename='partner-responses')

urlpatterns = [
    path('', include(router.urls)),
    path('profile/', PartnerProfileView.as_view(), name='partner-profile'),

    # ✅ Bemor ID bo‘yicha barcha javoblar uchun qo‘shimcha endpoint:
    path(
        'responses/patient/<int:patient_id>/',
        PartnerResponseViewSet.as_view({'get': 'patient_responses'}),
        name='partner-patient-responses',
    ),
]
