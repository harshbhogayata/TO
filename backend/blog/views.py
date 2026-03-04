from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from .models import Article
from .serializers import ArticleSerializer


class BlogListThrottle(ScopedRateThrottle):
    scope = 'blog_list'


@method_decorator(cache_page(60 * 5), name='dispatch')  # 5-minute cache
class ArticleListView(generics.ListAPIView):
    """GET /api/v1/blog/articles/ — Paginated resource list of articles."""
    serializer_class = ArticleSerializer
    permission_classes = [AllowAny]
    throttle_classes = [BlogListThrottle]
    queryset = Article.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get('category')
        if category and category != 'All Articles':
            qs = qs.filter(category=category)
        return qs
