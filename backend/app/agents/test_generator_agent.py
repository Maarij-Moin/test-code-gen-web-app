"""
Test Generator Agent — converts a TestPlan into concrete test file artifacts.

Responsibilities
----------------
- For each ``TestTarget`` in the plan, fetch related context from ChromaDB
  (delegating to ``retrieval_agent.retrieve_context``).
- Build a rich LLM prompt via ``prompt_service.generate_test_prompt``.
- Write a scaffold test file to disk (ready for the validation agent to run).
- Capture per-target generation status for the audit log.

Retry & repair integration
--------------------------
When called with ``failure_logs`` (non-None), this agent switches into
"repair mode": the failure output is injected into the prompt so the LLM
can correct the previous attempt.  The orchestrator handles the retry loop
(up to ``max_repair_attempts``).

LangGraph integration
---------------------
``run(state)`` is the node entry-point::

    graph.add_node("generator", test_generator_agent.run)

Reads:
    ``test_plan``     (TestPlan)
    ``repo_id``       (str)
    ``failure_logs``  (str | None)   — populated during repair cycles.

Writes:
    ``test_artifacts``  (list[GeneratedTestArtifact])
    ``generation_stats`` (dict)
    ``error``            (str | None)
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agents.planner_agent import TestPlan, TestTarget
from app.services.retrieval_service import retrieve_related_chunks
from app.services.vectorstore_service import load_vectorstore
from app.services.prompt_service import generate_test_prompt
from app.services.test_generation_service import (
    build_request_from_target,
    generate_test_file,
    GeneratedTestFile,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class GeneratedTestArtifact:
    """A single generated test file artifact (LLM-backed)."""

    target_file: str        # Source file this test covers.
    function_name: str      # Function/class under test.
    test_file_path: str     # Absolute path to the written test file.
    content: str            # Final validated content written to disk.
    prompt: str             # Full user prompt sent to the LLM (for audit).
    language: str
    framework: str
    intent: str
    priority: int
    generated_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )
    # LLM metadata
    llm_model: str = ""
    llm_provider: str = ""
    syntax_valid: bool = True
    # Populated during repair cycles
    repair_attempt: int = 0
    failure_logs_used: str | None = None


@dataclass
class GenerationStats:
    """Aggregated statistics for a generation run."""

    total_targets: int = 0
    generated: int = 0
    skipped: int = 0
    failed_targets: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_name(name: str) -> str:
    """Sanitise a string for use as a Python filename component.

    Args:
        name: Raw name (function name, file stem, etc.).

    Returns:
        Snake-case alphanumeric string.
    """
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", name or "test")
    return cleaned.strip("_") or "test"


def _scaffold_content(
    abs_file_path: str,
    function_name: str,
    language: str,
    framework: str,
) -> str:
    """Build a minimal but runnable test scaffold.

    The scaffold is committed to disk immediately.  When a real LLM is wired
    in, it will **replace** this content; until then it serves as a passing
    placeholder that keeps CI green.

    Args:
        abs_file_path:  Absolute path to the source file under test.
        function_name:  Function/method to test.
        language:       Programming language (e.g. "Python").
        framework:      Test framework (e.g. "pytest").

    Returns:
        Test file content string.
    """
    safe_fn = _safe_name(function_name)

    if language.lower() in {"javascript", "typescript", "js", "ts"}:
        # Jest scaffold
        return (
            f"// Auto-generated scaffold — replace with real assertions.\n"
            f"describe('{function_name}', () => {{\n"
            f"  it('should exist', () => {{\n"
            f"    // TODO: import and assert {function_name}\n"
            f"    expect(true).toBe(true);\n"
            f"  }});\n"
            f"}});\n"
        )

    # pytest scaffold (default)
    return (
        "# Auto-generated scaffold — replace with real assertions.\n"
        "import importlib.util\n"
        "import pathlib\n\n"
        f"_FILE = pathlib.Path(r\"{abs_file_path}\")\n\n"
        "def _load():\n"
        "    spec = importlib.util.spec_from_file_location('_mod', _FILE)\n"
        "    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]\n"
        "    assert spec and spec.loader\n"
        "    spec.loader.exec_module(mod)  # type: ignore[union-attr]\n"
        "    return mod\n\n"
        f"def test_{safe_fn}_exists():\n"
        "    mod = _load()\n"
        f"    assert hasattr(mod, '{function_name}'), (\n"
        f"        f\"Expected '{function_name}' to be defined in {{_FILE}}\"\n"
        "    )\n"
    )


def _resolve_test_dir(repo_path: str) -> Path:
    """Locate or create the auto-generated test directory.

    Args:
        repo_path: Absolute path to the repository root.

    Returns:
        Path object pointing to the test directory.
    """
    test_dir = Path(repo_path) / "auto_tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


# ---------------------------------------------------------------------------
# Core generation logic
# ---------------------------------------------------------------------------

def generate_for_target(
    target: TestTarget,
    repo_path: str,
    repo_id: str,
    *,
    failure_logs: str | None = None,
    repair_attempt: int = 0,
) -> GeneratedTestArtifact:
    """Generate a real LLM-backed test file for a single ``TestTarget``.

    Delegates to ``test_generation_service.generate_test_file`` which
    handles retrieval, prompt construction, LLM call, syntax validation,
    self-healing retry, and disk persistence.

    Args:
        target:         The test target describing the function to cover.
        repo_path:      Absolute path to the repository root.
        repo_id:        Chroma collection identifier.
        failure_logs:   Validation stdout/stderr from a previous attempt.
        repair_attempt: Which repair iteration we are on (0 = first).

    Returns:
        A populated ``GeneratedTestArtifact`` with real LLM-generated content.
    """
    logger.info(
        "[test_generator_agent] Generating for %s::%s (repair=%d)",
        target.file, target.function_name, repair_attempt,
    )

    # Build the generation request (includes ChromaDB retrieval)
    req = build_request_from_target(
        target=target,
        repo_id=repo_id,
        failure_logs=failure_logs,
        repair_attempt=repair_attempt,
    )

    # Call the real LLM-backed generation service
    gtf: GeneratedTestFile = generate_test_file(req, repo_path)

    logger.info(
        "[test_generator_agent] Generated %s. syntax_valid=%s retries=%d model=%s",
        gtf.test_file_path, gtf.syntax_valid, gtf.retry_count, gtf.llm_model,
    )

    return GeneratedTestArtifact(
        target_file=target.file,
        function_name=target.function_name,
        test_file_path=gtf.test_file_path,
        content=gtf.content,
        prompt=gtf.prompt_user,
        language=target.language,
        framework=target.framework,
        intent=target.intent,
        priority=target.priority,
        llm_model=gtf.llm_model,
        llm_provider=gtf.llm_provider,
        syntax_valid=gtf.syntax_valid,
        repair_attempt=repair_attempt,
        failure_logs_used=failure_logs,
    )


def generate_tests(
    plan: TestPlan,
    *,
    failure_logs: str | None = None,
    repair_attempt: int = 0,
) -> tuple[list[GeneratedTestArtifact], GenerationStats]:
    """Generate test artifacts for all targets in a plan.

    Args:
        plan:           The ``TestPlan`` produced by the planner agent.
        failure_logs:   Validation logs from a previous cycle (repair mode).
        repair_attempt: Which repair iteration (0 = initial generation).

    Returns:
        A tuple of (artifacts, stats).
    """
    logger.info(
        "[test_generator_agent] Generating %d target(s). repair_attempt=%d",
        len(plan.targets), repair_attempt,
    )

    artifacts: list[GeneratedTestArtifact] = []
    stats = GenerationStats(total_targets=len(plan.targets))

    for target in plan.sorted_targets():
        try:
            artifact = generate_for_target(
                target=target,
                repo_path=plan.repo_path,
                repo_id=plan.repo_id,
                failure_logs=failure_logs,
                repair_attempt=repair_attempt,
            )
            artifacts.append(artifact)
            stats.generated += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "[test_generator_agent] Failed for %s::%s: %s",
                target.file, target.function_name, exc,
            )
            stats.skipped += 1
            stats.failed_targets.append(f"{target.file}::{target.function_name}")

    logger.info(
        "[test_generator_agent] Done. generated=%d skipped=%d",
        stats.generated, stats.skipped,
    )
    return artifacts, stats


# ---------------------------------------------------------------------------
# LangGraph node adapter
# ---------------------------------------------------------------------------

def run(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node entry-point for the test generator.

    Reads from state:
        ``test_plan``    (TestPlan)     — required.
        ``repo_id``      (str)          — required.
        ``failure_logs`` (str | None)   — populated in repair cycles.
        ``repair_attempt`` (int)        — defaults to 0.

    Writes to state:
        ``test_artifacts``   (list[GeneratedTestArtifact])
        ``generation_stats`` (dict with total/generated/skipped counts)
        ``error``            (str | None)

    Args:
        state: Mutable LangGraph state dict.

    Returns:
        Updated state dict.
    """
    plan: TestPlan = state["test_plan"]
    failure_logs: str | None = state.get("failure_logs")
    repair_attempt: int = state.get("repair_attempt", 0)

    try:
        artifacts, stats = generate_tests(
            plan,
            failure_logs=failure_logs,
            repair_attempt=repair_attempt,
        )
        state["test_artifacts"] = artifacts
        state["generation_stats"] = {
            "total_targets": stats.total_targets,
            "generated": stats.generated,
            "skipped": stats.skipped,
            "failed_targets": stats.failed_targets,
            "repair_attempt": repair_attempt,
        }
        state.setdefault("error", None)
    except Exception as exc:  # noqa: BLE001
        msg = f"[test_generator_agent] node failed: {exc}"
        logger.exception(msg)
        state["test_artifacts"] = []
        state["generation_stats"] = {}
        state["error"] = msg

    return state
