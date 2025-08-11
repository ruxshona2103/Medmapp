from django.urls import path
from .views import CreateApplicationView, ApplicationStatusView, ServiceListView, OrderServiceView, OrderedServicesListView

urlpatterns = [
    path('api/application/create/', CreateApplicationView.as_view(), name='application-create'),
    path('api/application/status/', ApplicationStatusView.as_view(), name='application-status'),
    path('api/services/', ServiceListView.as_view(), name='service-list'),
    path('api/services/order/', OrderServiceView.as_view(), name='service-order'),
    path('api/services/ordered/', OrderedServicesListView.as_view(), name='ordered-services-list'),
]