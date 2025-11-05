from rest_framework.routers import DefaultRouter
from review.views import ReviewViewSet, BlogPostViewSet

router = DefaultRouter()
router.register("review", ReviewViewSet)
router.register("blog", BlogPostViewSet)
urlpatterns = router.urls
