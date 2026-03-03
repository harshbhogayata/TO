from django.apps import AppConfig


class CoursesConfig(AppConfig):
    name = 'courses'
    verbose_name = 'Learning Management System'

    def ready(self):
        import courses.signals  # noqa: F401 — register signal handlers
