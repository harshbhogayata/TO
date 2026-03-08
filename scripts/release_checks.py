"""Run reproducible launch-release checks from the current workspace environment."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / 'backend'
NPM = shutil.which('npm.cmd') or shutil.which('npm') or 'npm'
PYTHON = sys.executable


def run_step(label: str, command: list[str], cwd: Path) -> None:
    print(f'\n== {label} ==')
    print(' '.join(command))
    result = subprocess.run(command, cwd=cwd)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    run_step('Frontend Lint', [NPM, 'run', 'lint'], ROOT_DIR)
    run_step('Frontend Tests', [NPM, 'run', 'test'], ROOT_DIR)
    run_step('Backend Runtime Smoke', [PYTHON, 'scripts/runtime_smoke.py'], BACKEND_DIR)
    run_step(
        'Backend Django Check',
        [PYTHON, 'manage.py', 'check', '--settings=talentorbit.test_settings'],
        BACKEND_DIR,
    )
    run_step(
        'Backend Launch Tests',
        [
            PYTHON,
            'manage.py',
            'test',
            'tests.test_resume_parsing_contract',
            'developer.tests.test_webhooks',
            'tests.test_search',
            'tests.test_payments',
            '--settings=talentorbit.test_settings',
        ],
        BACKEND_DIR,
    )
    print('\nAll release checks passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
