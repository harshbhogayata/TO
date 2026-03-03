"""
search/apps.py
Django app configuration for the Search & Discovery engine.
Registers signals on ready() to auto-update search vectors on model save.
"""
from django.apps import AppConfig


class SearchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'search'
    verbose_name = 'Search & Discovery'

    def ready(self):
        import search.signals  # noqa: F401
