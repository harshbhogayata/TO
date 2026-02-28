from rest_framework import serializers
from .models import Article

class ArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ['id', 'category', 'readTime', 'title', 'excerpt', 'author', 'date', 'img', 'alt', 'created_at']
        read_only_fields = ['id', 'created_at']
