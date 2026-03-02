"""
Management command to create a logical backup of the database.

For Neon PostgreSQL, there are two backup strategies:

1. **Neon Built-in** (recommended for production):
   - Neon automatically provides point-in-time recovery (PITR)
   - Branch history retains data for your plan's retention period
   - Use the Neon Console to create named branches as backup snapshots
   - Zero configuration needed — it's automatic.

2. **Manual pg_dump** (this command — for local/export snapshots):
   - Runs `pg_dump` against the configured DATABASE_URL
   - Creates a timestamped SQL dump file
   - Useful for migration testing, local dev seeding, or external archival

Usage:
    python manage.py db_backup                     # dump to backend/backups/
    python manage.py db_backup --output /tmp/       # dump to custom dir
    python manage.py db_backup --format custom      # use pg_dump custom format
"""
import os
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create a logical backup (pg_dump) of the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', '-o',
            type=str,
            default=None,
            help='Output directory for the dump file. Defaults to backend/backups/',
        )
        parser.add_argument(
            '--format', '-f',
            type=str,
            default='plain',
            choices=['plain', 'custom', 'directory', 'tar'],
            help='pg_dump output format. Defaults to plain SQL.',
        )

    def handle(self, *args, **options):
        db_conf = settings.DATABASES.get('default', {})
        engine = db_conf.get('ENGINE', '')

        if 'postgresql' not in engine and 'postgis' not in engine:
            raise CommandError(
                f'This command only supports PostgreSQL. Current engine: {engine}'
            )

        # Build output path
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        ext = {'plain': 'sql', 'custom': 'dump', 'directory': '', 'tar': 'tar'}
        out_dir = options['output'] or str(Path(settings.BASE_DIR) / 'backups')
        os.makedirs(out_dir, exist_ok=True)

        fmt = options['format']
        filename = f'talentorbit_{timestamp}.{ext.get(fmt, "sql")}'
        out_path = os.path.join(out_dir, filename)

        # Build pg_dump command
        env = os.environ.copy()
        database_url = os.environ.get('DATABASE_URL', '')

        if database_url:
            # Use the connection URI directly
            cmd = ['pg_dump', database_url, f'--format={fmt}', f'--file={out_path}']
        else:
            host = db_conf.get('HOST', 'localhost')
            port = db_conf.get('PORT', '5432')
            name = db_conf.get('NAME', '')
            user = db_conf.get('USER', '')
            password = db_conf.get('PASSWORD', '')

            if password:
                env['PGPASSWORD'] = password

            cmd = [
                'pg_dump',
                f'--host={host}',
                f'--port={port}',
                f'--username={user}',
                f'--format={fmt}',
                f'--file={out_path}',
                name,
            ]

        self.stdout.write(f'Running backup: {" ".join(cmd[:3])}...')

        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                raise CommandError(f'pg_dump failed:\n{result.stderr}')
        except FileNotFoundError:
            raise CommandError(
                'pg_dump not found. Install PostgreSQL client tools or use Neon\'s '
                'built-in PITR for backups (zero config needed).'
            )

        # Check file size
        if fmt != 'directory':
            size = os.path.getsize(out_path)
            self.stdout.write(self.style.SUCCESS(
                f'Backup complete: {out_path} ({size / 1024:.1f} KB)'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f'Backup complete: {out_path}/'))

        self.stdout.write(
            '\nTip: Neon provides automatic point-in-time recovery.\n'
            'For production, rely on Neon PITR + named branches.\n'
            'This dump is for local testing and external archival.'
        )
