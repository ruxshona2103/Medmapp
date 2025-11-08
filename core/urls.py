from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import StageViewSet, TagViewSet
from .health_check import health_check, test_images

router = DefaultRouter()
router.register(r"stages", StageViewSet, basename="stages")
router.register(r"tags", TagViewSet, basename="tags")

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("test-images/", test_images, name="test-images"),
] + router.urls
