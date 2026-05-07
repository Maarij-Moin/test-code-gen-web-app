"""Validation agent for running test suites."""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    status: str
    output: str
    exit_code: int


def _run_command(command: list[str], cwd: str) -> ValidationResult:
    logger.info("[validation_agent] Running command: %s", " ".join(command))
    completed = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    status = "passed" if completed.returncode == 0 else "failed"
    return ValidationResult(status=status, output=completed.stdout, exit_code=completed.returncode)


def validate_tests(repo_path: str) -> ValidationResult:
    """Run pytest or jest based on project structure.

    Args:
        repo_path: Local repository path.

    Returns:
        ValidationResult with status and logs.
    """

    if os.path.exists(os.path.join(repo_path, "package.json")):
        return _run_command(["npm", "test", "--", "--runInBand"], cwd=repo_path)

    return _run_command(["pytest", "-q"], cwd=repo_path)
