from django.apps import AppConfig


class AssessmentsConfig(AppConfig):
    name = 'assessments'
    verbose_name = 'Assessments & Skill Verification'

    def ready(self):
        import assessments.signals  # noqa: F401
