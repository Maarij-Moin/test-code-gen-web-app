"""Validation and self-healing pipeline for generated tests."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job


logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    status: str
    attempts: int
    passed: bool
    failed: bool
    repaired: bool
    unrecoverable: bool
    stdout: str
    stderr: str
    failures: list[str]
    stack_traces: list[str]
    started_at: str
    completed_at: str


def _select_command(repo_path: str, language: str | None = None) -> list[str]:
    """Select the validation command based on repo structure or language hint."""

    lang = (language or "").lower()
    if lang in {"javascript", "js", "typescript", "ts"}:
        return ["npm", "test", "--", "--runInBand"]
    if lang == "java":
        return ["mvn", "-q", "test"]

    if os.path.exists(os.path.join(repo_path, "package.json")):
        return ["npm", "test", "--", "--runInBand"]
    if os.path.exists(os.path.join(repo_path, "pom.xml")):
        return ["mvn", "-q", "test"]

    return ["pytest", "-q"]


def _run_command(command: list[str], cwd: str, timeout_seconds: int) -> tuple[str, str, int]:
    """Run a subprocess safely with timeout and capture output."""

    logger.info("[validation] Running command: %s", " ".join(command))
    completed = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    return completed.stdout or "", completed.stderr or "", completed.returncode


def _parse_failures(output: str) -> tuple[list[str], list[str]]:
    """Extract failed assertions and stack traces from output."""

    failures = re.findall(r"AssertionError:.*", output)
    stack_traces = re.findall(r"Traceback[\s\S]+?(?=\n\n|$)", output)
    if "FAIL" in output:
        failures.append("FAIL marker detected")
    return failures, stack_traces


def _build_repair_prompt(output: str) -> str:
    """Build a repair prompt from validation output."""

    return (
        "Tests failed during validation. Analyze the logs and repair the tests.\n\n"
        f"Validation logs:\n{output}\n\n"
        "Return corrected test file content only."
    )


def _attempt_repair(repo_path: str, prompt: str) -> bool:
    """Placeholder repair hook. Integrate LLM-based repair here."""

    logger.warning("[validation] Repair requested. Prompt length=%d", len(prompt))
    # TODO: call LLM and write updated tests to disk.
    return False


async def _store_report(
    session: AsyncSession,
    repo_id: str,
    commit_sha: str | None,
    report: ValidationReport,
) -> None:
    """Persist validation report into the Job table."""

    job = Job(
        repo_id=repo_id,
        job_type="validation",
        status=report.status,
        commit_sha=commit_sha,
        payload=json.loads(json.dumps(asdict(report))),
    )
    session.add(job)
    await session.commit()


async def validate_and_repair(
    session: AsyncSession,
    repo_path: str,
    repo_id: str,
    commit_sha: str | None = None,
    language: str | None = None,
    max_retries: int = 3,
    timeout_seconds: int = 900,
) -> ValidationReport:
    """Run validation with retry-based repair loop.

    Returns structured ValidationReport.
    """

    attempts = 0
    started_at = datetime.utcnow().isoformat()
    stdout = ""
    stderr = ""
    failures: list[str] = []
    stack_traces: list[str] = []

    while attempts < max_retries:
        attempts += 1
        command = _select_command(repo_path, language)
        try:
            stdout, stderr, exit_code = _run_command(command, repo_path, timeout_seconds)
        except subprocess.TimeoutExpired:
            stderr = "Validation timeout exceeded."
            exit_code = 124

        output = "\n".join([stdout, stderr]).strip()
        failures, stack_traces = _parse_failures(output)

        if exit_code == 0:
            report = ValidationReport(
                status="passed",
                attempts=attempts,
                passed=True,
                failed=False,
                repaired=False,
                unrecoverable=False,
                stdout=stdout,
                stderr=stderr,
                failures=failures,
                stack_traces=stack_traces,
                started_at=started_at,
                completed_at=datetime.utcnow().isoformat(),
            )
            await _store_report(session, repo_id, commit_sha, report)
            return report

        prompt = _build_repair_prompt(output)
        repaired = _attempt_repair(repo_path, prompt)
        if not repaired:
            break

    report = ValidationReport(
        status="unrecoverable",
        attempts=attempts,
        passed=False,
        failed=True,
        repaired=False,
        unrecoverable=True,
        stdout=stdout,
        stderr=stderr,
        failures=failures,
        stack_traces=stack_traces,
        started_at=started_at,
        completed_at=datetime.utcnow().isoformat(),
    )
    await _store_report(session, repo_id, commit_sha, report)
    return report
