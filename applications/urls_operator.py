from django.urls import path
from .views_operator import OperatorApplicationsView, ChangeApplicationStatusView

urlpatterns = [
    path('operator/applications/', OperatorApplicationsView.as_view(), name='operator_applications'),
    path('operator/applications/<int:pk>/change-status/', ChangeApplicationStatusView.as_view(), name='change_status'),
]
