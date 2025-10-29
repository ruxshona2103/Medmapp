from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PartnerPatientViewSet,
    PartnerProfileView,
    PartnerResponseDocumentViewSet, OperatorSendResponseView, PartnerSendResponseView, ResponsesMyListView,
)

router = DefaultRouter()
router.register(r'patients', PartnerPatientViewSet, basename='partner-patients')
router.register(r'responses', PartnerResponseDocumentViewSet, basename='partner-responses')

urlpatterns = [
    path('', include(router.urls)),

    # Profile
    path('partner/', PartnerProfileView.as_view(), name='partner-profile'),

    # Operator → Patient
    path(
        "responses/operator/send/<int:patient_id>/",
        OperatorSendResponseView.as_view(),
        name="responses-operator-send"
    ),

    # Partner → Operator
    path(
        "responses/partner/send/<int:patient_id>/",
        PartnerSendResponseView.as_view(),
        name="responses-partner-send"
    ),

    # All roles → See their own files
    path(
        "responses/my/",
        ResponsesMyListView.as_view(),
        name="responses-my"
    ),
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