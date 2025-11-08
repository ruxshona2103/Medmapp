from rest_framework.routers import DefaultRouter
from review.views import ReviewViewSet, BlogPostViewSet

router = DefaultRouter()
router.register("review", ReviewViewSet, basename="review")
router.register("blog", BlogPostViewSet, basename="blog")
urlpatterns = router.urls
