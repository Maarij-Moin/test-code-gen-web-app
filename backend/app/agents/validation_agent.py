"""
Validation Agent — runs the generated test suite and drives the repair loop.

Responsibilities
----------------
- Select the correct test runner command (pytest / npm test / mvn) based on
  the language of the generated artifacts.
- Execute each test file in a subprocess with a configurable timeout.
- Parse stdout/stderr to extract failure messages and stack traces.
- Return a structured ``ValidationResult`` that the orchestrator uses to
  decide whether to trigger another generation/repair cycle.

Repair-loop protocol
--------------------
The agent itself does NOT call back into the generator.  Instead it returns
``needs_repair=True`` along with the captured ``failure_logs`` string.  The
orchestrator is responsible for looping and passing ``failure_logs`` into the
next ``test_generator_agent`` call.

LangGraph integration
---------------------
``run(state)`` is the node entry-point::

    graph.add_node("validator", validation_agent.run)

Reads:
    ``test_artifacts``  (list[GeneratedTestArtifact])
    ``test_plan``       (TestPlan)
    ``repair_attempt``  (int)

Writes:
    ``validation_result`` (ValidationResult)
    ``failure_logs``      (str | None)
    ``error``             (str | None)
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.agents.test_generator_agent import GeneratedTestArtifact
from app.agents.planner_agent import TestPlan

logger = logging.getLogger(__name__)

# Default subprocess timeout (seconds) — overridable via env.
_DEFAULT_TIMEOUT: int = int(os.getenv("VALIDATION_TIMEOUT_SECONDS", "120"))


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class ArtifactValidation:
    """Validation outcome for a single generated test file."""

    test_file_path: str
    exit_code: int
    stdout: str
    stderr: str
    passed: bool
    failures: list[str]
    stack_traces: list[str]


@dataclass
class ValidationResult:
    """Aggregated validation outcome for an entire generation cycle."""

    status: str                      # "passed" | "failed" | "timeout" | "error"
    passed: bool
    needs_repair: bool
    repair_attempt: int
    total_files: int
    passed_files: int
    failed_files: int
    failure_logs: str                # Concatenated output from all failing files.
    artifact_results: list[ArtifactValidation] = field(default_factory=list)
    validated_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Command selection
# ---------------------------------------------------------------------------

def _select_command(test_file_path: str, language: str, repo_path: str) -> list[str]:
    """Choose the test runner command for a given artifact.

    Priority:
    1. Explicit language hint.
    2. ``package.json`` presence (JS/TS project).
    3. ``pom.xml`` presence (Java/Maven project).
    4. Default: pytest.

    Args:
        test_file_path: Absolute path to the test file to run.
        language:       Detected language string from the test artifact.
        repo_path:      Repository root (used for project-file detection).

    Returns:
        Command list suitable for ``subprocess.run``.
    """
    lang = (language or "").lower()
    if lang in {"javascript", "typescript", "js", "ts"}:
        return ["npm", "test", "--", "--testPathPattern", os.path.basename(test_file_path), "--runInBand"]
    if lang == "java":
        return ["mvn", "-q", "test"]
    if os.path.exists(os.path.join(repo_path, "package.json")):
        return ["npm", "test", "--", "--testPathPattern", os.path.basename(test_file_path), "--runInBand"]
    if os.path.exists(os.path.join(repo_path, "pom.xml")):
        return ["mvn", "-q", "test"]
    # Default: pytest on just the generated file
    return ["pytest", test_file_path, "-q", "--tb=short"]


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------

def _parse_output(combined: str) -> tuple[list[str], list[str]]:
    """Extract failure messages and stack traces from combined test output.

    Args:
        combined: Concatenated stdout + stderr from the test runner.

    Returns:
        (failures, stack_traces) — lists of extracted strings.
    """
    failures: list[str] = []
    stack_traces: list[str] = []

    # pytest assertion failures
    failures.extend(re.findall(r"AssertionError:.*", combined))
    # pytest FAILED lines  (e.g. "FAILED tests/test_foo.py::test_bar - ...")
    failures.extend(re.findall(r"^FAILED\s+.+", combined, re.MULTILINE))
    # Jest failure prefix
    failures.extend(re.findall(r"● .*", combined))
    # Python tracebacks
    stack_traces.extend(re.findall(r"Traceback \(most recent call last\)[\s\S]+?(?=\n\n|\Z)", combined))

    # Deduplicate while preserving order
    seen: set[str] = set()
    failures = [f for f in failures if not (f in seen or seen.add(f))]  # type: ignore[func-returns-value]

    return failures, stack_traces


# ---------------------------------------------------------------------------
# Single-artifact runner
# ---------------------------------------------------------------------------

def _run_artifact(
    artifact: GeneratedTestArtifact,
    repo_path: str,
    timeout: int,
) -> ArtifactValidation:
    """Run the test runner against a single generated test file.

    Args:
        artifact:   The generated test artifact to validate.
        repo_path:  Repository root (used as cwd for the subprocess).
        timeout:    Maximum seconds to wait for the process.

    Returns:
        An ``ArtifactValidation`` describing the outcome.
    """
    command = _select_command(artifact.test_file_path, artifact.language, repo_path)
    logger.info(
        "[validation_agent] Running: %s (timeout=%ds)",
        " ".join(command), timeout,
    )

    try:
        proc = subprocess.run(
            command,
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        logger.warning(
            "[validation_agent] Timeout (%ds) running %s",
            timeout, artifact.test_file_path,
        )
        return ArtifactValidation(
            test_file_path=artifact.test_file_path,
            exit_code=124,
            stdout="",
            stderr=f"Validation timed out after {timeout}s.",
            passed=False,
            failures=["Timeout"],
            stack_traces=[],
        )
    except FileNotFoundError as exc:
        logger.error("[validation_agent] Test runner not found: %s", exc)
        return ArtifactValidation(
            test_file_path=artifact.test_file_path,
            exit_code=-1,
            stdout="",
            stderr=str(exc),
            passed=False,
            failures=[f"Runner not found: {exc}"],
            stack_traces=[],
        )

    combined = f"{stdout}\n{stderr}".strip()
    failures, stack_traces = _parse_output(combined)
    passed = (exit_code == 0)

    logger.info(
        "[validation_agent] %s → %s (exit=%d, failures=%d)",
        artifact.test_file_path, "PASS" if passed else "FAIL", exit_code, len(failures),
    )

    return ArtifactValidation(
        test_file_path=artifact.test_file_path,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        passed=passed,
        failures=failures,
        stack_traces=stack_traces,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_artifacts(
    artifacts: list[GeneratedTestArtifact],
    repo_path: str,
    *,
    repair_attempt: int = 0,
    timeout: int = _DEFAULT_TIMEOUT,
) -> ValidationResult:
    """Run validation against all generated test artifacts.

    Args:
        artifacts:      List of artifacts produced by the generator agent.
        repo_path:      Repository root (used as cwd and for project detection).
        repair_attempt: Which repair cycle this validation is for.
        timeout:        Per-process timeout in seconds.

    Returns:
        A ``ValidationResult`` summarising pass/fail status for the cycle.
    """
    if not artifacts:
        logger.warning("[validation_agent] No artifacts to validate.")
        return ValidationResult(
            status="passed",
            passed=True,
            needs_repair=False,
            repair_attempt=repair_attempt,
            total_files=0,
            passed_files=0,
            failed_files=0,
            failure_logs="",
        )

    logger.info(
        "[validation_agent] Validating %d artifact(s). repair_attempt=%d",
        len(artifacts), repair_attempt,
    )

    results: list[ArtifactValidation] = []
    all_failure_logs: list[str] = []

    for artifact in artifacts:
        av = _run_artifact(artifact, repo_path, timeout)
        results.append(av)
        if not av.passed:
            combined = f"FILE: {av.test_file_path}\n{av.stdout}\n{av.stderr}".strip()
            all_failure_logs.append(combined)

    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count
    overall_passed = failed_count == 0
    failure_logs_str = "\n\n---\n\n".join(all_failure_logs)

    status = "passed" if overall_passed else "failed"
    needs_repair = not overall_passed

    logger.info(
        "[validation_agent] Result: %s. passed=%d/%d needs_repair=%s",
        status.upper(), passed_count, len(results), needs_repair,
    )

    return ValidationResult(
        status=status,
        passed=overall_passed,
        needs_repair=needs_repair,
        repair_attempt=repair_attempt,
        total_files=len(results),
        passed_files=passed_count,
        failed_files=failed_count,
        failure_logs=failure_logs_str,
        artifact_results=results,
    )


# ---------------------------------------------------------------------------
# LangGraph node adapter
# ---------------------------------------------------------------------------

def run(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node entry-point for the validation agent.

    Reads from state:
        ``test_artifacts``  (list[GeneratedTestArtifact]) — required.
        ``test_plan``       (TestPlan)                    — for repo_path.
        ``repair_attempt``  (int)                         — defaults to 0.

    Writes to state:
        ``validation_result`` (ValidationResult)
        ``failure_logs``      (str | None)   — set when needs_repair=True.
        ``error``             (str | None)

    Args:
        state: Mutable LangGraph state dict.

    Returns:
        Updated state dict.
    """
    artifacts: list[GeneratedTestArtifact] = state.get("test_artifacts", [])
    plan: TestPlan = state["test_plan"]
    repair_attempt: int = state.get("repair_attempt", 0)

    try:
        result = validate_artifacts(
            artifacts=artifacts,
            repo_path=plan.repo_path,
            repair_attempt=repair_attempt,
        )
        state["validation_result"] = result
        state["failure_logs"] = result.failure_logs if result.needs_repair else None
        state.setdefault("error", None)
    except Exception as exc:  # noqa: BLE001
        msg = f"[validation_agent] node failed: {exc}"
        logger.exception(msg)
        state["validation_result"] = None
        state["failure_logs"] = None
        state["error"] = msg

    return state
