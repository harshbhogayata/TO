from django.db import models

class Course(models.Model):
    category = models.CharField(max_length=100)
    module_name = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    duration = models.CharField(max_length=50)
    img_url = models.URLField(max_length=500)
    url = models.URLField(max_length=500, blank=True, help_text='External course URL (opens in new tab)')
    is_coming_soon = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.title} ({self.category})"
