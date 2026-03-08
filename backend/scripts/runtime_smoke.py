"""Runtime smoke checks for launch-critical backend imports."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault('DATABASE_URL', '')
os.environ.setdefault('SENTRY_DSN', '')
os.environ.setdefault('SECRET_KEY', 'runtime-smoke-secret')
os.environ.setdefault('DEBUG', 'True')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'talentorbit.test_settings')

REQUIRED_MODULES = [
    'django',
    'celery',
    'channels',
    'drf_spectacular',
    'oauth2_provider',
]
TARGET_IMPORTS = [
    'talentorbit.settings',
    'talentorbit.urls',
    'intelligence.urls',
    'developer.urls',
]


def check_import(module_name: str) -> tuple[bool, str]:
    try:
        importlib.import_module(module_name)
        return True, f'OK  {module_name}'
    except Exception as exc:  # pragma: no cover - smoke output path
        return False, f'FAIL {module_name}: {exc.__class__.__name__}: {exc}'


def main() -> int:
    print(f'Runtime smoke root: {ROOT_DIR}')
    failures: list[str] = []

    for module_name in REQUIRED_MODULES + TARGET_IMPORTS:
        ok, message = check_import(module_name)
        print(message)
        if not ok:
            failures.append(message)

    if failures:
        print('\nRuntime smoke failed.')
        return 1

    print('\nRuntime smoke passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
