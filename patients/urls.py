# patients/urls.py
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from .views import (
    PatientListCreateView, PatientDetailView, PatientMeView,
    PatientMeAvatarView, PatientAvatarView,
    ChangeStageView, PatientDocumentCreateView, PatientDocumentDeleteView,
    ResponseLettersListView, TagListView, TagDeleteView, StageListView,
    ContractApproveView
)

urlpatterns = [
    path('', PatientListCreateView.as_view()),
    path('<int:pk>/', PatientDetailView.as_view()),
    path('me/', PatientMeView.as_view()),
    path('me/avatar/', PatientMeAvatarView.as_view()),
    path('<int:pk>/avatar/', PatientAvatarView.as_view()),
    path('<int:patient_id>/change-stage/', ChangeStageView.as_view()),
    path('<int:patient_id>/documents/', PatientDocumentCreateView.as_view()),
    path('documents/<int:pk>/', PatientDocumentDeleteView.as_view()),
    path('response-letters/', ResponseLettersListView.as_view()),
    path('tags/', TagListView.as_view()),
    path('tags/<int:pk>/', TagDeleteView.as_view()),
    path('stages/', StageListView.as_view()),
    path('contracts/<int:contract_id>/approve/', ContractApproveView.as_view()),
]
if settings.DEBUG:  # faqat dev rejimida
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)