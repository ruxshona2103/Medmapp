from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HotelViewSet,
    BookingViewSet,
    VisaCreateView,
    VisaRetrieveView,
    TransferCreateView,
    TransferRetrieveView,
    TranslatorCreateView,
    TranslatorRetrieveView,
    SimCardCreateView,
    SimCardRetrieveView,
    OrdersMeView,  # Qo‘shilishi kerak
    OrdersListView, PatientOrdersDetailView,  # Qo‘shilishi kerak
)

router = DefaultRouter()
router.register(r"hotels", HotelViewSet, basename="hotel")
router.register(r"hotel-bookings", BookingViewSet, basename="hotel-booking")

urlpatterns = [
    # --- VISA ---
    path("visa/", VisaCreateView.as_view(), name="visa-create"),
    path("visa/<int:pk>/", VisaRetrieveView.as_view(), name="visa-detail"),
    # --- TRANSFER ---
    path("transfer/", TransferCreateView.as_view(), name="transfer-create"),
    path("transfer/<int:pk>/", TransferRetrieveView.as_view(), name="transfer-detail"),
    # --- TRANSLATOR ---
    path("translator/", TranslatorCreateView.as_view(), name="translator-create"),
    path(
        "translator/<int:pk>/",
        TranslatorRetrieveView.as_view(),
        name="translator-detail",
    ),
    # --- SIM CARD ---
    path("simcard/", SimCardCreateView.as_view(), name="simcard-create"),
    path("simcard/<int:pk>/", SimCardRetrieveView.as_view(), name="simcard-detail"),
    # --- HOTEL & BOOKINGS (via router) ---
    path("", include(router.urls)),
    # --- ORDERS ---
    path('orders/me/', OrdersMeView.as_view(), name='orders-me'),
    path('orders/', OrdersListView.as_view(), name='orders-list'),
    path('orders/<int:id>/', PatientOrdersDetailView.as_view(), name='orders-by-patient'),
]
