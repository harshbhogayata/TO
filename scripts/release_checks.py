"""Run reproducible release checks from the current workspace environment.

Supports full-platform validation and focused workflow checks so repairs can be
done one use case at a time.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / 'backend'
NPM = shutil.which('npm.cmd') or shutil.which('npm') or 'npm'
DEFAULT_PYTHON = Path(sys.executable)
BACKEND_VENV_PYTHON = BACKEND_DIR / 'venv' / 'Scripts' / 'python.exe'
ROOT_VENV_PYTHON = ROOT_DIR / 'venv' / 'Scripts' / 'python.exe'
REQUIRED_BACKEND_MODULES = ('django', 'celery', 'channels')


@dataclass(frozen=True)
class Step:
    label: str
    command: tuple[str, ...]
    cwd: Path


@dataclass(frozen=True)
class FocusGroup:
    description: str
    steps: tuple[Step, ...]


def supports_modules(python_path: Path, module_names: tuple[str, ...]) -> bool:
    if not python_path.exists():
        return False

    probe = (
        'import importlib.util, sys; '
        f"mods = {module_names!r}; "
        'sys.exit(0 if all(importlib.util.find_spec(name) for name in mods) else 1)'
    )
    result = subprocess.run(
        (str(python_path), '-c', probe),
        cwd=ROOT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def select_backend_python() -> str:
    candidates = [ROOT_VENV_PYTHON, BACKEND_VENV_PYTHON, DEFAULT_PYTHON]
    for candidate in candidates:
        if supports_modules(candidate, REQUIRED_BACKEND_MODULES):
            return str(candidate)
    return str(DEFAULT_PYTHON)


BACKEND_PYTHON = select_backend_python()


def run_step(label: str, command: tuple[str, ...], cwd: Path) -> None:
    print(f'\n== {label} ==')
    print(' '.join(command))
    result = subprocess.run(command, cwd=cwd)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


COMMON_BACKEND_STEPS = (
    Step('Backend Runtime Smoke', (BACKEND_PYTHON, 'scripts/runtime_smoke.py'), BACKEND_DIR),
    Step(
        'Backend Django Check',
        (BACKEND_PYTHON, 'manage.py', 'check', '--settings=talentorbit.test_settings'),
        BACKEND_DIR,
    ),
)


FOCUS_GROUPS: dict[str, FocusGroup] = {
    'full': FocusGroup(
        description='Full release gate across frontend and launch-critical backend flows.',
        steps=(
            Step('Frontend Lint', (NPM, 'run', 'lint'), ROOT_DIR),
            Step('Frontend Tests', (NPM, 'run', 'test'), ROOT_DIR),
            *COMMON_BACKEND_STEPS,
            Step(
                'Backend Launch Tests',
                (
                    BACKEND_PYTHON,
                    'manage.py',
                    'test',
                    'tests.test_resume_parsing_contract',
                    'developer.tests.test_webhooks',
                    'tests.test_search',
                    'tests.test_payments',
                    '--settings=talentorbit.test_settings',
                ),
                BACKEND_DIR,
            ),
        ),
    ),
    'onboarding': FocusGroup(
        description='Talent registration, login, verification, password reset, resume parsing.',
        steps=(
            Step(
                'Frontend Onboarding Tests',
                (
                    NPM,
                    'run',
                    'test',
                    '--',
                    'src/services/api.test.js',
                    'src/store/authStore.test.js',
                    'src/components/ProtectedRoute.test.jsx',
                ),
                ROOT_DIR,
            ),
            *COMMON_BACKEND_STEPS,
            Step(
                'Backend Onboarding Tests',
                (
                    BACKEND_PYTHON,
                    'manage.py',
                    'test',
                    'tests.test_resume_parsing_contract',
                    'tests.test_auth_security',
                    '--settings=talentorbit.test_settings',
                ),
                BACKEND_DIR,
            ),
        ),
    ),
    'jobs': FocusGroup(
        description='Job discovery, applications, saved jobs, company job CRUD, talent search.',
        steps=(
            *COMMON_BACKEND_STEPS,
            Step(
                'Backend Jobs And Search Tests',
                (
                    BACKEND_PYTHON,
                    'manage.py',
                    'test',
                    'jobs.tests',
                    'tests.test_search',
                    '--settings=talentorbit.test_settings',
                ),
                BACKEND_DIR,
            ),
        ),
    ),
    'billing': FocusGroup(
        description='Checkout, Stripe webhooks, subscription lifecycle, invoices.',
        steps=(
            Step(
                'Frontend Billing Tests',
                (
                    NPM,
                    'run',
                    'test',
                    '--',
                    'src/store/paymentStore.test.js',
                    'src/pages/SubscriptionPlans.test.jsx',
                ),
                ROOT_DIR,
            ),
            *COMMON_BACKEND_STEPS,
            Step(
                'Backend Billing Tests',
                (
                    BACKEND_PYTHON,
                    'manage.py',
                    'test',
                    'tests.test_payments',
                    '--settings=talentorbit.test_settings',
                ),
                BACKEND_DIR,
            ),
        ),
    ),
    'growth': FocusGroup(
        description='Company CRM pipeline, sponsored campaigns, and company analytics surfaces.',
        steps=(
            Step(
                'Frontend Growth Tests',
                (
                    NPM,
                    'run',
                    'test',
                    '--',
                    'src/store/paymentStore.growth.test.js',
                    'src/pages/SponsoredPosts.test.jsx',
                    'src/pages/CRMPipeline.test.jsx',
                    'src/pages/CompanyAnalytics.test.jsx',
                ),
                ROOT_DIR,
            ),
            *COMMON_BACKEND_STEPS,
            Step(
                'Backend Growth Tests',
                (
                    BACKEND_PYTHON,
                    'manage.py',
                    'test',
                    'tests.test_growth_workflow',
                    '--settings=talentorbit.test_settings',
                ),
                BACKEND_DIR,
            ),
        ),
    ),
    'messaging': FocusGroup(
        description='Inbox, notifications, message threads, send flows, realtime delivery.',
        steps=(
            *COMMON_BACKEND_STEPS,
            Step(
                'Backend Messaging Tests',
                (
                    BACKEND_PYTHON,
                    'manage.py',
                    'test',
                    'tests.test_messaging',
                    'tests.test_realtime',
                    '--settings=talentorbit.test_settings',
                ),
                BACKEND_DIR,
            ),
        ),
    ),
    'admin': FocusGroup(
        description='Admin console, compliance, privacy, team and audit workflows.',
        steps=(
            *COMMON_BACKEND_STEPS,
            Step(
                'Backend Admin And Compliance Tests',
                (
                    BACKEND_PYTHON,
                    'manage.py',
                    'test',
                    'tests.test_admin_api',
                    'compliance.tests.test_audit_log',
                    'compliance.tests.test_consent',
                    'compliance.tests.test_gdpr_deletion',
                    'compliance.tests.test_gdpr_export',
                    'compliance.tests.test_policies',
                    'compliance.tests.test_team',
                    '--settings=talentorbit.test_settings',
                ),
                BACKEND_DIR,
            ),
        ),
    ),
    'developer': FocusGroup(
        description='API keys, webhooks, OAuth apps, delivery logs, portal limits.',
        steps=(
            *COMMON_BACKEND_STEPS,
            Step(
                'Backend Developer Platform Tests',
                (
                    BACKEND_PYTHON,
                    'manage.py',
                    'test',
                    'developer.tests.test_api_keys',
                    'developer.tests.test_oauth_apps',
                    'developer.tests.test_tasks',
                    'developer.tests.test_webhooks',
                    '--settings=talentorbit.test_settings',
                ),
                BACKEND_DIR,
            ),
        ),
    ),
    'ai': FocusGroup(
        description='AI resume parsing contracts, company AI generation, and analytics access boundaries.',
        steps=(
            *COMMON_BACKEND_STEPS,
            Step(
                'Backend AI And Intelligence Tests',
                (
                    BACKEND_PYTHON,
                    'manage.py',
                    'test',
                    'tests.test_resume_parsing_contract',
                    'tests.test_ai_workflow',
                    '--settings=talentorbit.test_settings',
                ),
                BACKEND_DIR,
            ),
        ),
    ),
    'learning': FocusGroup(
        description='Course progression, lesson resume state, assessment attempts, results, and invitations.',
        steps=(
            Step(
                'Frontend Learning And Assessment Tests',
                (
                    NPM,
                    'run',
                    'test',
                    '--',
                    'src/pages/MyLearning.test.jsx',
                    'src/pages/AssessmentPlayer.test.jsx',
                    'src/pages/AssessmentResults.test.jsx',
                    'src/pages/MyAssessments.test.jsx',
                ),
                ROOT_DIR,
            ),
            *COMMON_BACKEND_STEPS,
            Step(
                'Backend Learning And Assessment Tests',
                (
                    BACKEND_PYTHON,
                    'manage.py',
                    'test',
                    'tests.test_learning_workflow',
                    '--settings=talentorbit.test_settings',
                ),
                BACKEND_DIR,
            ),
        ),
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--focus',
        action='append',
        default=[],
        metavar='GROUP',
        help='Workflow group to run. May be supplied multiple times.',
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List available focus groups and exit.',
    )
    return parser.parse_args()


def normalise_focus_names(raw_focus: list[str]) -> list[str]:
    if not raw_focus:
        return ['full']

    names: list[str] = []
    for value in raw_focus:
        for name in value.split(','):
            cleaned = name.strip().lower()
            if cleaned:
                names.append(cleaned)
    return names


def iter_steps(focus_names: list[str]) -> list[Step]:
    ordered_steps: list[Step] = []
    seen: set[tuple[str, tuple[str, ...], str]] = set()

    for focus_name in focus_names:
        group = FOCUS_GROUPS.get(focus_name)
        if group is None:
            choices = ', '.join(sorted(FOCUS_GROUPS))
            raise SystemExit(f'Unknown focus group "{focus_name}". Available: {choices}')
        for step in group.steps:
            signature = (step.label, step.command, str(step.cwd))
            if signature in seen:
                continue
            seen.add(signature)
            ordered_steps.append(step)

    return ordered_steps


def main() -> int:
    args = parse_args()

    if args.list:
        print('Available focus groups:\n')
        for name in sorted(FOCUS_GROUPS):
            print(f'- {name}: {FOCUS_GROUPS[name].description}')
        print(f'\nBackend interpreter: {BACKEND_PYTHON}')
        return 0

    focus_names = normalise_focus_names(args.focus)
    steps = iter_steps(focus_names)

    print(f'Running focus group(s): {", ".join(focus_names)}')
    print(f'Using backend interpreter: {BACKEND_PYTHON}')
    for step in steps:
        run_step(step.label, step.command, step.cwd)

    print('\nRelease checks passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

