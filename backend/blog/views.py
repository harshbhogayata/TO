from rest_framework import generics
from rest_framework.permissions import AllowAny
from .models import Article
from .serializers import ArticleSerializer

class ArticleListView(generics.ListAPIView):
    """GET /api/v1/blog/articles/ — Paginated resource list of articles."""
    serializer_class = ArticleSerializer
    permission_classes = [AllowAny]
    queryset = Article.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get('category')
        if category and category != 'All Articles':
            qs = qs.filter(category=category)
        return qs
