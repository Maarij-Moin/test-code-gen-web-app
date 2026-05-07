"""
Test Validation Service — syntax + runtime validation pipeline.

This module provides three levels of validation:

1. **Syntax validation** — pure static check, no subprocess (delegates to
   ``test_generation_service.validate_syntax``).  Runs in-process; fast.

2. **Runtime validation** — subprocess execution of the test runner.
   Language-detected command (pytest / jest / mvn).  Full stdout/stderr
   capture with configurable timeout.

3. **LLM-based repair** — when runtime validation fails, builds a repair
   prompt from the failure logs and calls back into ``test_generation_service``
   to regenerate the file.  Limited by ``max_repair_attempts``.

All three levels return a ``ValidationReport`` with a unified status field
and structured failure extraction.

Integration
-----------
``validate_generated_file(gtf, repo_path, …)`` is the single entry-point.
It orchestrates all three levels.  The calling agent/orchestrator only needs
to check ``report.passed`` and ``report.needs_repair``.

``validate_and_repair_batch(files, repo_path, …)`` processes an entire batch,
tracking per-file outcomes and aggregating into ``BatchValidationResult``.

All DB persistence from the old ``validation_service`` is reproduced here —
the existing ``_store_report`` pattern is kept so callers can optionally
persist results to the ``Job`` table.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.services.test_generation_service import (
    GeneratedTestFile,
    GenerationRequest,
    generate_test_file,
    validate_syntax,
    _extract_code,
    _select_system_prompt,
    _build_user_prompt,
    _resolve_output_path,
)
from app.services.llm_service import complete as llm_complete

logger = logging.getLogger(__name__)

# Per-file subprocess timeout (seconds) — overridable via env var.
_DEFAULT_TIMEOUT: int = int(os.environ.get("VALIDATION_TIMEOUT_SECONDS", "120"))
# Repair ceiling for the repair loop.
_DEFAULT_MAX_REPAIRS: int = int(os.environ.get("VALIDATION_MAX_REPAIRS", "3"))


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class ValidationReport:
    """Full validation outcome for a single generated test file."""

    # Identity
    test_file_path: str
    target_file: str
    function_name: str
    language: str

    # Outcome
    status: str          # "passed" | "syntax_failed" | "runtime_failed" | "repaired" | "unrecoverable"
    passed: bool
    syntax_valid: bool
    needs_repair: bool
    repair_attempts: int

    # Runtime detail
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    failures: list[str] = field(default_factory=list)
    stack_traces: list[str] = field(default_factory=list)
    failure_logs: str = ""

    # Timing
    started_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )
    completed_at: str = ""


@dataclass
class BatchValidationResult:
    """Aggregated outcome for a batch of generated test files."""

    reports: list[ValidationReport] = field(default_factory=list)
    repaired_files: list[GeneratedTestFile] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.reports)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.reports if r.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def overall_passed(self) -> bool:
        return self.failed == 0


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------

def _select_command(
    test_file_path: str,
    language: str,
    repo_path: str,
) -> list[str]:
    """Choose the test runner command for a specific test file.

    Priority:
        1. Language hint.
        2. ``package.json`` presence (JS/TS project root).
        3. ``pom.xml`` presence (Java/Maven project).
        4. Default: pytest.

    Args:
        test_file_path: Absolute path to the test file.
        language:       Detected language string.
        repo_path:      Repository root (for project-file detection).

    Returns:
        Subprocess command list.
    """
    lang = (language or "").lower()

    if lang in {"javascript", "js"}:
        return ["npx", "jest", "--testPathPattern", os.path.basename(test_file_path), "--no-coverage", "--forceExit"]
    if lang in {"typescript", "ts"}:
        return ["npx", "jest", "--testPathPattern", os.path.basename(test_file_path), "--no-coverage", "--forceExit"]
    if lang == "java":
        return ["mvn", "-q", "test", f"-Dtest={os.path.splitext(os.path.basename(test_file_path))[0]}"]

    # Project-file detection for ambiguous cases
    if os.path.exists(os.path.join(repo_path, "package.json")):
        return ["npx", "jest", "--testPathPattern", os.path.basename(test_file_path), "--no-coverage", "--forceExit"]
    if os.path.exists(os.path.join(repo_path, "pom.xml")):
        return ["mvn", "-q", "test"]

    # Default: pytest with short tracebacks, targeting the specific file
    return ["pytest", test_file_path, "-q", "--tb=short", "--no-header"]


def _run_subprocess(
    command: list[str],
    cwd: str,
    timeout: int,
) -> tuple[str, str, int]:
    """Execute *command* as a subprocess and return (stdout, stderr, exit_code).

    Args:
        command:  Command + args list.
        cwd:      Working directory.
        timeout:  Max seconds to wait.

    Returns:
        (stdout, stderr, exit_code) tuple.
        On ``TimeoutExpired``: ("", "Timeout after {n}s", 124).
        On ``FileNotFoundError``: ("", "Command not found: ...", -1).
    """
    logger.info("[test_validation_service] Running: %s", " ".join(command))
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.stdout or "", proc.stderr or "", proc.returncode
    except subprocess.TimeoutExpired:
        logger.warning("[test_validation_service] Timeout (%ds) for: %s", timeout, " ".join(command))
        return "", f"Validation timed out after {timeout}s.", 124
    except FileNotFoundError as exc:
        logger.error("[test_validation_service] Runner not found: %s", exc)
        return "", f"Test runner not found: {exc}", -1


# ---------------------------------------------------------------------------
# Failure parsing
# ---------------------------------------------------------------------------

def _parse_failures(stdout: str, stderr: str) -> tuple[list[str], list[str]]:
    """Extract human-readable failure messages and stack traces.

    Args:
        stdout: Captured stdout from the test runner.
        stderr: Captured stderr from the test runner.

    Returns:
        (failures, stack_traces) — lists of extracted strings.
    """
    combined = f"{stdout}\n{stderr}"
    failures: list[str] = []
    stack_traces: list[str] = []

    # pytest FAILED lines
    failures.extend(re.findall(r"^FAILED\s+.+", combined, re.MULTILINE))
    # pytest AssertionError
    failures.extend(re.findall(r"AssertionError:.*", combined))
    # Jest failure markers
    failures.extend(re.findall(r"● .+", combined))
    # Java test failures
    failures.extend(re.findall(r"FAILED: .+", combined))
    # Python tracebacks
    stack_traces.extend(re.findall(
        r"Traceback \(most recent call last\)[\s\S]+?(?=\n\n|\Z)", combined
    ))

    # Deduplicate while preserving order
    seen: set[str] = set()
    failures = [f for f in failures if not (f in seen or seen.add(f))]  # type: ignore[func-returns-value]

    return failures, stack_traces


# ---------------------------------------------------------------------------
# LLM repair
# ---------------------------------------------------------------------------

def _build_repair_prompt(
    gtf: GeneratedTestFile,
    failure_logs: str,
    repair_attempt: int,
) -> str:
    """Build the user prompt for an LLM-based repair call.

    Args:
        gtf:            The failed ``GeneratedTestFile``.
        failure_logs:   Combined stdout + stderr from the failed run.
        repair_attempt: Which repair cycle this is.

    Returns:
        User prompt string.
    """
    return (
        f"FILE: {gtf.test_file_path}\n"
        f"LANGUAGE: {gtf.language}   FRAMEWORK: {gtf.framework}\n\n"
        f"--- FAILING TEST FILE (attempt {repair_attempt}) ---\n"
        f"{gtf.content}\n\n"
        f"--- FAILURE LOGS ---\n"
        f"{failure_logs[:2000]}\n\n"
        "--- TASK ---\n"
        "Fix the test file so all tests pass. "
        "Output ONLY the corrected raw source code, no markdown, no explanations."
    )


def _llm_repair(
    gtf: GeneratedTestFile,
    repo_path: str,
    failure_logs: str,
    repair_attempt: int,
) -> GeneratedTestFile | None:
    """Attempt an LLM-based repair of *gtf*.

    Calls the LLM with the failure logs injected, validates the response,
    and writes the repaired file to the same path on success.

    Args:
        gtf:            The ``GeneratedTestFile`` to repair.
        repo_path:      Repository root (for file writing).
        failure_logs:   Combined test output from the failed run.
        repair_attempt: Which repair cycle this is.

    Returns:
        A new ``GeneratedTestFile`` on successful repair, or None on failure.
    """
    logger.info(
        "[test_validation_service] LLM repair attempt %d for %s",
        repair_attempt, gtf.test_file_path,
    )
    system_prompt = _select_system_prompt(gtf.language, gtf.framework)
    user_prompt = _build_repair_prompt(gtf, failure_logs, repair_attempt)

    try:
        resp = llm_complete(system_prompt=system_prompt, user_prompt=user_prompt)
    except RuntimeError as exc:
        logger.error("[test_validation_service] LLM repair call failed: %s", exc)
        return None

    code = _extract_code(resp.content, gtf.language)
    valid, error_msg = validate_syntax(code, gtf.language)

    if not valid:
        logger.warning(
            "[test_validation_service] Repaired code still has syntax error: %s", error_msg
        )
        return None

    # Overwrite the test file in place
    from pathlib import Path
    path = Path(gtf.test_file_path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(code, encoding="utf-8")
    tmp.replace(path)

    logger.info(
        "[test_validation_service] Repair written to %s (%d bytes).", path, len(code)
    )

    from dataclasses import replace
    return replace(
        gtf,
        content=code,
        syntax_valid=True,
        retry_count=gtf.retry_count + repair_attempt,
        llm_model=resp.model,
        llm_provider=resp.provider,
        prompt_tokens=resp.prompt_tokens,
        completion_tokens=resp.completion_tokens,
        latency_ms=resp.latency_ms,
    )


# ---------------------------------------------------------------------------
# Primary validation entry-point
# ---------------------------------------------------------------------------

def validate_generated_file(
    gtf: GeneratedTestFile,
    repo_path: str,
    *,
    max_repair_attempts: int = _DEFAULT_MAX_REPAIRS,
    timeout: int = _DEFAULT_TIMEOUT,
) -> tuple[ValidationReport, GeneratedTestFile]:
    """Validate (and optionally repair) a single generated test file.

    Flow
    ----
    1. Syntax check — fast, in-process.
    2. If syntax invalid → mark ``syntax_failed``, return immediately
       (no point running the runner on broken code).
    3. Runtime execution — subprocess.
    4. If passes → ``passed``, done.
    5. If fails → build failure logs → LLM repair → re-run.
    6. After ``max_repair_attempts`` → ``unrecoverable``.

    Args:
        gtf:                 The ``GeneratedTestFile`` to validate.
        repo_path:           Repository root (cwd for subprocess).
        max_repair_attempts: Maximum repair cycles.
        timeout:             Per-subprocess timeout in seconds.

    Returns:
        (ValidationReport, final_GeneratedTestFile) — the report and the
        best available version of the test file (may be repaired).
    """
    started = datetime.now(tz=timezone.utc).isoformat()

    def _make_report(
        status: str,
        passed: bool,
        syntax_valid: bool,
        needs_repair: bool,
        repair_attempts: int,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
        failures: list[str] | None = None,
        stack_traces: list[str] | None = None,
        failure_logs: str = "",
    ) -> ValidationReport:
        return ValidationReport(
            test_file_path=gtf.test_file_path,
            target_file=gtf.target_file,
            function_name=gtf.function_name,
            language=gtf.language,
            status=status,
            passed=passed,
            syntax_valid=syntax_valid,
            needs_repair=needs_repair,
            repair_attempts=repair_attempts,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            failures=failures or [],
            stack_traces=stack_traces or [],
            failure_logs=failure_logs,
            started_at=started,
            completed_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------ #
    # Step 1 — Syntax check                                               #
    # ------------------------------------------------------------------ #
    syntax_ok, syntax_err = validate_syntax(gtf.content, gtf.language)
    if not syntax_ok:
        logger.warning(
            "[test_validation_service] Syntax invalid for %s: %s",
            gtf.test_file_path, syntax_err,
        )
        return (
            _make_report(
                "syntax_failed", False, False, needs_repair=False,
                repair_attempts=0, failure_logs=syntax_err,
            ),
            gtf,
        )

    # ------------------------------------------------------------------ #
    # Steps 2-4 — Runtime execution + repair loop                        #
    # ------------------------------------------------------------------ #
    current_gtf = gtf
    repair_attempts = 0

    for attempt in range(max_repair_attempts + 1):
        command = _select_command(current_gtf.test_file_path, current_gtf.language, repo_path)
        stdout, stderr, exit_code = _run_subprocess(command, repo_path, timeout)
        failures, stack_traces = _parse_failures(stdout, stderr)
        failure_logs = f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}".strip()

        if exit_code == 0:
            status = "repaired" if repair_attempts > 0 else "passed"
            logger.info(
                "[test_validation_service] %s %s (repairs=%d)",
                status.upper(), current_gtf.test_file_path, repair_attempts,
            )
            return (
                _make_report(
                    status, True, True, needs_repair=False,
                    repair_attempts=repair_attempts, exit_code=exit_code,
                    stdout=stdout, stderr=stderr,
                    failures=failures, stack_traces=stack_traces,
                ),
                current_gtf,
            )

        logger.warning(
            "[test_validation_service] Runtime failed (attempt %d/%d). exit=%d failures=%d",
            attempt, max_repair_attempts, exit_code, len(failures),
        )

        if attempt >= max_repair_attempts:
            break

        # LLM repair
        repaired = _llm_repair(current_gtf, repo_path, failure_logs, attempt + 1)
        repair_attempts += 1
        if repaired:
            current_gtf = repaired
        else:
            logger.warning(
                "[test_validation_service] LLM repair #%d returned None — continuing.",
                repair_attempts,
            )

    logger.error(
        "[test_validation_service] Unrecoverable: %s after %d repair(s).",
        current_gtf.test_file_path, repair_attempts,
    )
    return (
        _make_report(
            "unrecoverable", False, syntax_ok, needs_repair=True,
            repair_attempts=repair_attempts, exit_code=exit_code,
            stdout=stdout, stderr=stderr, failures=failures,
            stack_traces=stack_traces, failure_logs=failure_logs,
        ),
        current_gtf,
    )


# ---------------------------------------------------------------------------
# Batch validation
# ---------------------------------------------------------------------------

def validate_and_repair_batch(
    files: list[GeneratedTestFile],
    repo_path: str,
    *,
    max_repair_attempts: int = _DEFAULT_MAX_REPAIRS,
    timeout: int = _DEFAULT_TIMEOUT,
) -> BatchValidationResult:
    """Validate a list of generated test files, repairing failures with the LLM.

    Args:
        files:               Generated test files to validate.
        repo_path:           Repository root (cwd for subprocesses).
        max_repair_attempts: Maximum repair cycles per file.
        timeout:             Per-subprocess timeout in seconds.

    Returns:
        ``BatchValidationResult`` with per-file reports and repaired file list.
    """
    batch_result = BatchValidationResult()

    logger.info(
        "[test_validation_service] Batch validation: %d file(s). max_repairs=%d",
        len(files), max_repair_attempts,
    )

    for gtf in files:
        report, final_gtf = validate_generated_file(
            gtf,
            repo_path,
            max_repair_attempts=max_repair_attempts,
            timeout=timeout,
        )
        batch_result.reports.append(report)
        if final_gtf is not gtf:
            batch_result.repaired_files.append(final_gtf)

    logger.info(
        "[test_validation_service] Batch complete. passed=%d/%d repaired=%d",
        batch_result.passed, batch_result.total, len(batch_result.repaired_files),
    )
    return batch_result
