# compliance/tests/__init__.py
# Disconnect PostgreSQL-specific search vector signals at test-package import
# time. These signals use SearchVector (Postgres-only) and poison SQLite
# transactions when they fail inside Django TestCase's atomic wrapper.
from django.db.models.signals import post_save
from search.signals import (
    update_job_search_vector,
    update_talent_search_vector,
    update_company_search_vector,
)
from jobs.models import JobPost
from accounts.models import TalentProfile, CompanyProfile

post_save.disconnect(update_job_search_vector, sender=JobPost)
post_save.disconnect(update_talent_search_vector, sender=TalentProfile)
post_save.disconnect(update_company_search_vector, sender=CompanyProfile)
