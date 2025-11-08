from rest_framework.routers import DefaultRouter
from .views import StageViewSet, TagViewSet

router = DefaultRouter()
router.register(r"stages", StageViewSet, basename="stages")
router.register(r"tags", TagViewSet, basename="tags")

