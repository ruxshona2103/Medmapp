# patients/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('patients/', views.PatientListView.as_view(), name='patient-list'),
    path('patients/create/', views.PatientCreateView.as_view(), name='patient-create'),
    path('patients/<int:pk>/', views.PatientDetailView.as_view(), name='patient-detail'),
    path('patients/me/', views.PatientMeView.as_view(), name='patient-me'),
    path('patients/<int:patient_id>/change-stage/', views.ChangeStageView.as_view(), name='change-stage'),
    path('patients/<int:patient_id>/documents/', views.PatientDocumentCreateView.as_view(), name='document-create'),
    path('documents/<int:id>/', views.PatientDocumentDeleteView.as_view(), name='document-delete'),
    path('stages/', views.StageListView.as_view(), name='stage-list'),
    path('tags/', views.TagListView.as_view(), name='tag-list'),
    path('tags/<int:pk>/', views.TagDeleteView.as_view(), name='tag-delete'),
]