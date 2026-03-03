"""
search/management/commands/rebuild_search_vectors.py

Management command to backfill search vectors for all existing records.
Run this once after deploying the search_vector migration, and optionally
on a schedule if you ever suspect vectors are stale.

Usage:
    python manage.py rebuild_search_vectors              # All models
    python manage.py rebuild_search_vectors --model jobs  # Jobs only
    python manage.py rebuild_search_vectors --model talent
    python manage.py rebuild_search_vectors --model companies
"""
import time

from django.core.management.base import BaseCommand
from django.contrib.postgres.search import SearchVector
from django.db.models import Value


class Command(BaseCommand):
    help = 'Rebuild SearchVectorField for all searchable models (JobPost, TalentProfile, CompanyProfile).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            choices=['jobs', 'talent', 'companies', 'all'],
            default='all',
            help='Which model to rebuild vectors for (default: all).',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Number of records to update per batch (default: 500).',
        )

    def handle(self, *args, **options):
        model = options['model']
        batch_size = options['batch_size']

        if model in ('jobs', 'all'):
            self._rebuild_jobs(batch_size)
        if model in ('talent', 'all'):
            self._rebuild_talent(batch_size)
        if model in ('companies', 'all'):
            self._rebuild_companies(batch_size)

        self.stdout.write(self.style.SUCCESS('Search vector rebuild complete.'))

    def _rebuild_jobs(self, batch_size):
        from jobs.models import JobPost

        total = JobPost.objects.count()
        self.stdout.write(f'Rebuilding search vectors for {total} JobPosts...')
        start = time.monotonic()

        updated = 0
        for job in JobPost.objects.select_related('company__company_profile').iterator(chunk_size=batch_size):
            skills_text = ' '.join(job.skills_required) if job.skills_required else ''
            try:
                company_name = job.company.company_profile.legal_name
            except Exception:
                company_name = job.company.full_name or ''

            JobPost.objects.filter(pk=job.pk).update(
                search_vector=(
                    SearchVector('title', weight='A', config='english')
                    + SearchVector(Value(skills_text), weight='A', config='english')
                    + SearchVector('location', weight='B', config='english')
                    + SearchVector('description', weight='B', config='english')
                    + SearchVector('requirements', weight='C', config='english')
                    + SearchVector('responsibilities', weight='C', config='english')
                    + SearchVector(Value(company_name), weight='C', config='english')
                )
            )
            updated += 1
            if updated % batch_size == 0:
                self.stdout.write(f'  ...{updated}/{total} jobs')

        elapsed = time.monotonic() - start
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ {updated} JobPosts rebuilt in {elapsed:.1f}s'
        ))

    def _rebuild_talent(self, batch_size):
        from accounts.models import TalentProfile

        total = TalentProfile.objects.count()
        self.stdout.write(f'Rebuilding search vectors for {total} TalentProfiles...')
        start = time.monotonic()

        updated = 0
        for tp in TalentProfile.objects.select_related('user').iterator(chunk_size=batch_size):
            skills_text = ' '.join(tp.skills) if tp.skills else ''
            full_name = tp.user.full_name or ''

            TalentProfile.objects.filter(pk=tp.pk).update(
                search_vector=(
                    SearchVector(Value(skills_text), weight='A', config='english')
                    + SearchVector(Value(full_name), weight='A', config='english')
                    + SearchVector('bio', weight='B', config='english')
                    + SearchVector('location', weight='B', config='english')
                )
            )
            updated += 1
            if updated % batch_size == 0:
                self.stdout.write(f'  ...{updated}/{total} profiles')

        elapsed = time.monotonic() - start
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ {updated} TalentProfiles rebuilt in {elapsed:.1f}s'
        ))

    def _rebuild_companies(self, batch_size):
        from accounts.models import CompanyProfile

        total = CompanyProfile.objects.count()
        self.stdout.write(f'Rebuilding search vectors for {total} CompanyProfiles...')
        start = time.monotonic()

        updated = 0
        for cp in CompanyProfile.objects.iterator(chunk_size=batch_size):
            CompanyProfile.objects.filter(pk=cp.pk).update(
                search_vector=(
                    SearchVector('legal_name', weight='A', config='english')
                    + SearchVector('industry', weight='A', config='english')
                    + SearchVector('mission_statement', weight='B', config='english')
                    + SearchVector('headquarters', weight='B', config='english')
                )
            )
            updated += 1
            if updated % batch_size == 0:
                self.stdout.write(f'  ...{updated}/{total} companies')

        elapsed = time.monotonic() - start
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ {updated} CompanyProfiles rebuilt in {elapsed:.1f}s'
        ))
