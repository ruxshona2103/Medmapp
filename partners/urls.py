# partners/urls.py
# ===============================================================
# HAMKOR PANEL - URLs
# ===============================================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PartnerPatientViewSet,
    PartnerProfileView,
    PartnerResponseDocumentViewSet,
)

router = DefaultRouter()
router.register(r'patients', PartnerPatientViewSet, basename='partner-patients')
router.register(r'responses', PartnerResponseDocumentViewSet, basename='partner-responses')

urlpatterns = [
    path('', include(router.urls)),

    # Profile
    path('profile/', PartnerProfileView.as_view(), name='partner-profile'),
]

# ===============================================================
# ENDPOINT'LAR:
# ===============================================================
"""
✅ Bemorlar:
GET    /api/v1/partner/patients/                         - Ro'yxat
GET    /api/v1/partner/patients/{id}/                    - Detail
PATCH  /api/v1/partner/patients/{id}/change-stage/      - Bosqich o'zgartirish
POST   /api/v1/partner/patients/{id}/upload-response/   - Javob xati yuklash

✅ Profil:
GET    /api/v1/partner/profile/                          - Profil
PATCH  /api/v1/partner/profile/                          - Yangilash

✅ Javob xatlari:
GET    /api/v1/partner/responses/                        - Ro'yxat
GET    /api/v1/partner/responses/{id}/                   - Detail
"""