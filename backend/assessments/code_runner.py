"""
assessments/code_runner.py
Phase 7 — Sandboxed Code Execution Service

Integrates with Judge0 CE (self-hosted or cloud) for secure, sandboxed execution
of user-submitted code during assessments. Supports multiple programming languages
with configurable time and memory limits.

Architecture:
    1. User submits code answer → Answer model stores raw code
    2. Celery task calls CodeExecutionService.run_test_cases()
    3. Each test case is submitted as a Judge0 submission (batched)
    4. Results are polled asynchronously until all complete
    5. Answer is graded based on test case pass/fail ratio

Security:
    - Code runs in isolated Docker containers via Judge0
    - Per-submission time limits (default 5s, max 30s)
    - Per-submission memory limits (default 256MB, max 512MB)
    - Network access disabled in Judge0 config
    - No filesystem persistence between submissions

Judge0 API Reference: https://judge0.com/#api
Self-hosted setup:  docker-compose in infra/judge0/
"""

import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

JUDGE0_API_URL = getattr(settings, 'JUDGE0_API_URL', 'http://localhost:2358')
JUDGE0_API_KEY = getattr(settings, 'JUDGE0_API_KEY', '')
JUDGE0_AUTHN_HEADER = getattr(settings, 'JUDGE0_AUTHN_HEADER', 'X-Auth-Token')

# Maximum limits (safety caps — these override per-question settings)
MAX_TIME_LIMIT_S = 30.0
MAX_MEMORY_LIMIT_KB = 512_000  # 512 MB
MAX_COMPILATION_TIME_S = 15.0
MAX_BATCH_SIZE = 20           # Judge0 batch submission limit

# Polling
POLL_INTERVAL_S = 0.5
POLL_MAX_WAIT_S = 60.0


class Judge0Status(IntEnum):
    """Judge0 submission status codes."""
    IN_QUEUE = 1
    PROCESSING = 2
    ACCEPTED = 3              # Correct output
    WRONG_ANSWER = 4
    TIME_LIMIT_EXCEEDED = 5
    COMPILATION_ERROR = 6
    RUNTIME_ERROR_SIGSEGV = 7
    RUNTIME_ERROR_SIGXFSZ = 8
    RUNTIME_ERROR_SIGFPE = 9
    RUNTIME_ERROR_SIGABRT = 10
    RUNTIME_ERROR_NZEC = 11
    RUNTIME_ERROR_OTHER = 12
    INTERNAL_ERROR = 13
    EXEC_FORMAT_ERROR = 14

    @classmethod
    def is_terminal(cls, status_id: int) -> bool:
        return status_id >= 3

    @classmethod
    def is_accepted(cls, status_id: int) -> bool:
        return status_id == cls.ACCEPTED


# ─── Language mapping ─────────────────────────────────────────────────────────
# Maps our internal language identifiers to Judge0 language IDs.
# Judge0 CE language list: GET /languages

LANGUAGE_MAP = {
    'python': 71,        # Python 3.8.1
    'python3': 71,
    'javascript': 63,    # Node.js 12.14.0
    'nodejs': 63,
    'java': 62,          # Java (OpenJDK 13.0.1)
    'cpp': 54,           # C++ (GCC 9.2.0)
    'c++': 54,
    'c': 50,             # C (GCC 9.2.0)
    'csharp': 51,        # C# (Mono 6.6.0.161)
    'c#': 51,
    'go': 60,            # Go 1.13.5
    'rust': 73,          # Rust 1.40.0
    'ruby': 72,          # Ruby 2.7.0
    'typescript': 74,    # TypeScript 3.7.4
    'php': 68,           # PHP 7.4.1
    'swift': 83,         # Swift 5.2.3
    'kotlin': 78,        # Kotlin 1.3.70
    'sql': 82,           # SQL (SQLite 3.27.2)
    'bash': 46,          # Bash 5.0.0
    'shell': 46,
}


@dataclass
class TestCaseResult:
    """Result of executing a single test case."""
    test_case_index: int
    passed: bool
    status_id: int
    status_description: str
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    compile_output: Optional[str] = None
    time_seconds: Optional[float] = None
    memory_kb: Optional[int] = None
    expected_output: Optional[str] = None
    actual_output: Optional[str] = None
    points: float = 0.0
    max_points: float = 0.0


@dataclass
class ExecutionResult:
    """Aggregated result of all test cases for a code submission."""
    passed: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    total_points: float
    max_points: float
    score_percentage: float
    compilation_error: Optional[str] = None
    test_results: list = field(default_factory=list)
    execution_time_total_s: float = 0.0
    peak_memory_kb: int = 0

    @property
    def has_compilation_error(self) -> bool:
        return self.compilation_error is not None


class Judge0Error(Exception):
    """Raised when Judge0 API returns an error or is unreachable."""
    pass


class CodeExecutionService:
    """
    Client for Judge0 CE sandboxed code execution.

    Designed to be used from Celery tasks for async grading:
        result = CodeExecutionService().run_test_cases(
            source_code='print(input())',
            language='python',
            test_cases=[
                {'input': 'hello', 'expected_output': 'hello', 'points': 10},
            ],
            time_limit_ms=5000,
            memory_limit_mb=256,
        )
    """

    def __init__(self, api_url: str = None, api_key: str = None):
        self.api_url = (api_url or JUDGE0_API_URL).rstrip('/')
        self.api_key = api_key or JUDGE0_API_KEY
        self._session = requests.Session()
        self._session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        if self.api_key:
            self._session.headers[JUDGE0_AUTHN_HEADER] = self.api_key

    # ── Public API ────────────────────────────────────────────────────────

    def health_check(self) -> dict:
        """Check Judge0 availability. Returns system info or raises."""
        try:
            resp = self._session.get(
                f'{self.api_url}/system_info',
                timeout=5,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise Judge0Error(f'Judge0 health check failed: {e}') from e

    def run_test_cases(
        self,
        source_code: str,
        language: str,
        test_cases: list,
        time_limit_ms: int = 5000,
        memory_limit_mb: int = 256,
    ) -> ExecutionResult:
        """
        Execute source code against all test cases and return graded results.

        Args:
            source_code: User-submitted code string.
            language: Programming language identifier (see LANGUAGE_MAP).
            test_cases: List of dicts with keys: input, expected_output, points.
            time_limit_ms: Per-test time limit in milliseconds.
            memory_limit_mb: Per-test memory limit in megabytes.

        Returns:
            ExecutionResult with per-test and aggregate results.

        Raises:
            Judge0Error: If Judge0 is unreachable or returns an API error.
            ValueError: If language is not supported.
        """
        language_id = self._resolve_language(language)
        time_limit_s = min(time_limit_ms / 1000.0, MAX_TIME_LIMIT_S)
        memory_limit_kb = min(memory_limit_mb * 1024, MAX_MEMORY_LIMIT_KB)

        if not test_cases:
            return ExecutionResult(
                passed=True, total_tests=0, passed_tests=0, failed_tests=0,
                total_points=0.0, max_points=0.0, score_percentage=100.0,
            )

        # Submit test cases in batches (Judge0 batch limit)
        all_tokens = []
        for batch_start in range(0, len(test_cases), MAX_BATCH_SIZE):
            batch = test_cases[batch_start:batch_start + MAX_BATCH_SIZE]
            submissions = [
                {
                    'source_code': source_code,
                    'language_id': language_id,
                    'stdin': tc.get('input', ''),
                    'expected_output': tc.get('expected_output', ''),
                    'cpu_time_limit': time_limit_s,
                    'cpu_extra_time': 1.0,
                    'wall_time_limit': time_limit_s * 3,
                    'memory_limit': memory_limit_kb,
                    'compilation_cpu_time_limit': MAX_COMPILATION_TIME_S,
                    'enable_network': False,
                    'enable_per_process_and_thread_time_limit': True,
                    'max_processes_and_or_threads': 30,
                }
                for tc in batch
            ]
            tokens = self._submit_batch(submissions)
            all_tokens.extend(tokens)

        # Poll until all submissions are complete
        results = self._poll_results(all_tokens)

        # Grade
        return self._grade_results(results, test_cases)

    def get_supported_languages(self) -> list:
        """Return list of supported language identifiers."""
        return list(LANGUAGE_MAP.keys())

    # ── Internal methods ──────────────────────────────────────────────────

    def _resolve_language(self, language: str) -> int:
        lang_lower = language.lower().strip()
        language_id = LANGUAGE_MAP.get(lang_lower)
        if language_id is None:
            raise ValueError(
                f'Unsupported language: {language!r}. '
                f'Supported: {", ".join(sorted(set(LANGUAGE_MAP.keys())))}'
            )
        return language_id

    def _submit_batch(self, submissions: list) -> list:
        """Submit a batch of submissions. Returns list of tokens."""
        try:
            resp = self._session.post(
                f'{self.api_url}/submissions/batch',
                json={'submissions': submissions},
                params={'base64_encoded': 'false', 'wait': 'false'},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return [item['token'] for item in data]
        except requests.RequestException as e:
            raise Judge0Error(f'Batch submission failed: {e}') from e
        except (KeyError, TypeError) as e:
            raise Judge0Error(f'Unexpected Judge0 response format: {e}') from e

    def _poll_results(self, tokens: list) -> list:
        """Poll Judge0 until all submissions reach a terminal state."""
        pending = set(range(len(tokens)))
        results = [None] * len(tokens)
        elapsed = 0.0

        while pending and elapsed < POLL_MAX_WAIT_S:
            time.sleep(POLL_INTERVAL_S)
            elapsed += POLL_INTERVAL_S

            # Batch get — max 20 tokens per request
            pending_list = sorted(pending)
            for batch_start in range(0, len(pending_list), MAX_BATCH_SIZE):
                batch_indices = pending_list[batch_start:batch_start + MAX_BATCH_SIZE]
                batch_tokens = [tokens[i] for i in batch_indices]
                token_str = ','.join(batch_tokens)

                try:
                    resp = self._session.get(
                        f'{self.api_url}/submissions/batch',
                        params={
                            'tokens': token_str,
                            'base64_encoded': 'false',
                            'fields': (
                                'token,status,stdout,stderr,compile_output,'
                                'time,memory,exit_code'
                            ),
                        },
                        timeout=15,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    submissions = data.get('submissions', data) if isinstance(data, dict) else data

                    for idx, submission in zip(batch_indices, submissions):
                        status = submission.get('status', {})
                        status_id = status.get('id', 0)
                        if Judge0Status.is_terminal(status_id):
                            results[idx] = submission
                            pending.discard(idx)

                except requests.RequestException:
                    logger.warning(
                        'Judge0 poll failed (elapsed=%.1fs, pending=%d)',
                        elapsed, len(pending),
                    )

        # Mark timed-out submissions
        for idx in pending:
            results[idx] = {
                'status': {'id': Judge0Status.TIME_LIMIT_EXCEEDED, 'description': 'Poll timeout'},
                'stdout': None,
                'stderr': 'Execution polling timed out.',
                'compile_output': None,
                'time': None,
                'memory': None,
            }

        return results

    def _grade_results(self, results: list, test_cases: list) -> ExecutionResult:
        """Grade Judge0 results against expected outputs."""
        test_results = []
        total_points = 0.0
        max_points = 0.0
        passed_count = 0
        compilation_error = None
        peak_memory = 0
        total_time = 0.0

        for i, (result, tc) in enumerate(zip(results, test_cases)):
            status = result.get('status', {})
            status_id = status.get('id', 0)
            status_desc = status.get('description', 'Unknown')
            tc_points = float(tc.get('points', 1.0))
            max_points += tc_points

            # Check for compilation error (affects all test cases)
            if status_id == Judge0Status.COMPILATION_ERROR:
                compilation_error = (
                    result.get('compile_output', '') or
                    result.get('stderr', '') or
                    'Compilation failed'
                )

            stdout = (result.get('stdout') or '').rstrip('\n')
            expected = (tc.get('expected_output', '') or '').rstrip('\n')
            passed = Judge0Status.is_accepted(status_id)

            # If Judge0 says accepted but output doesn't match, override
            if passed and stdout != expected:
                passed = False
                status_id = Judge0Status.WRONG_ANSWER
                status_desc = 'Wrong Answer'

            if passed:
                passed_count += 1
                total_points += tc_points

            exec_time = float(result.get('time') or 0)
            exec_memory = int(result.get('memory') or 0)
            total_time += exec_time
            peak_memory = max(peak_memory, exec_memory)

            test_results.append(TestCaseResult(
                test_case_index=i,
                passed=passed,
                status_id=status_id,
                status_description=status_desc,
                stdout=stdout[:2000] if stdout else None,
                stderr=(result.get('stderr') or '')[:2000] or None,
                compile_output=(result.get('compile_output') or '')[:2000] or None,
                time_seconds=exec_time or None,
                memory_kb=exec_memory or None,
                expected_output=expected[:500] if expected else None,
                actual_output=stdout[:500] if stdout else None,
                points=tc_points if passed else 0.0,
                max_points=tc_points,
            ))

        failed_count = len(test_cases) - passed_count
        score_pct = (total_points / max_points * 100) if max_points > 0 else 0.0

        return ExecutionResult(
            passed=failed_count == 0,
            total_tests=len(test_cases),
            passed_tests=passed_count,
            failed_tests=failed_count,
            total_points=total_points,
            max_points=max_points,
            score_percentage=round(score_pct, 2),
            compilation_error=compilation_error,
            test_results=test_results,
            execution_time_total_s=round(total_time, 3),
            peak_memory_kb=peak_memory,
        )


# ─── Module-level convenience instance ────────────────────────────────────────
# Uses settings from Django conf. Import and use directly:
#     from assessments.code_runner import code_runner
#     result = code_runner.run_test_cases(...)

code_runner = CodeExecutionService()
