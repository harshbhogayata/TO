from django.db import models

class Article(models.Model):
    category = models.CharField(max_length=100)
    readTime = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    excerpt = models.TextField()
    author = models.CharField(max_length=150)
    date = models.CharField(max_length=50)
    img = models.URLField(max_length=500)
    alt = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
