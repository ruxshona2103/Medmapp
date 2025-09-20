# consultations/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"conversations", views.ConversationViewSet)
router.register(r"summaries", views.DoctorSummaryViewSet)
router.register(r"prescriptions", views.PrescriptionViewSet)

# XATOLIK BO'LGAN QATORGA 'basename' QO'SHILDI
router.register(r"messages", views.MessageViewSet, basename="message")


urlpatterns = [
    path("", include(router.urls)),
]
