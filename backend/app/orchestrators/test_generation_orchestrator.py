"""
Test Generation Orchestrator — drives the full autonomous QA pipeline.

This module is the central coordinator for the Autonomous AI QA Platform.
It chains all five agents in the correct order, manages the repair loop,
captures a structured audit trail, and exposes both a synchronous interface
(``run_pipeline``) and an async-compatible wrapper (``run_pipeline_async``).

Pipeline stages
---------------
1. **Diff**       → ``diff_agent``            — pull repo, detect changes.
2. **Planner**    → ``planner_agent``          — build a prioritised test plan.
3. **Generator**  → ``test_generator_agent``   — generate test file scaffolds.
4. **Validator**  → ``validation_agent``       — run tests; detect failures.
5. **Repair loop** (3 → 4, up to ``max_repair_attempts``)
6. **PR Agent**   → ``pr_agent``              — build the PR summary report.

LangGraph readiness
-------------------
Every agent exposes a ``run(state: dict) -> dict`` interface.  The orchestrator
calls them sequentially for now.  To migrate to a full LangGraph ``StateGraph``
replace the sequential calls with::

    graph = StateGraph(PipelineState)
    graph.add_node("diff",      diff_agent.run)
    graph.add_node("planner",   planner_agent.run)
    graph.add_node("generator", test_generator_agent.run)
    graph.add_node("validator", validation_agent.run)
    graph.add_node("pr",        pr_agent.run)
    # add edges + conditional repair loop
    app = graph.compile()
    result = app.invoke(initial_state)

The ``PipelineState`` TypedDict defined here can be used directly as the
LangGraph state schema once you add the ``from langgraph.graph import StateGraph``
import.

Audit log
---------
Every stage transition is recorded in ``state["audit_log"]`` — a list of
``AuditEntry`` dicts — so you can reconstruct the full pipeline timeline for
any run.

Usage
-----
Synchronous (from a Celery task or CLI)::

    from app.orchestrators.test_generation_orchestrator import run_pipeline
    result = run_pipeline(repo_path="/app/repo/myproject", repo_id="repo_abc123")

Asynchronous (from FastAPI or a background task)::

    from app.orchestrators.test_generation_orchestrator import run_pipeline_async
    result = await run_pipeline_async(repo_path=..., repo_id=...)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, TypedDict

from app.agents import diff_agent, planner_agent, test_generator_agent, validation_agent, pr_agent
from app.agents.diff_agent import DiffResult
from app.agents.planner_agent import TestPlan
from app.agents.test_generator_agent import GeneratedTestArtifact
from app.agents.validation_agent import ValidationResult
from app.agents.pr_agent import PullRequestSummary

logger = logging.getLogger(__name__)

# Maximum repair-and-regeneration cycles before the orchestrator gives up.
DEFAULT_MAX_REPAIR_ATTEMPTS: int = 3


# ---------------------------------------------------------------------------
# State schema (LangGraph-compatible TypedDict)
# ---------------------------------------------------------------------------

class PipelineState(TypedDict, total=False):
    """Mutable state dict passed through every agent node.

    All keys are optional at the start of the pipeline; each agent populates
    its output keys before the next agent reads them.
    """
    # Inputs
    repo_path: str
    repo_id: str
    pull: bool
    max_repair_attempts: int

    # Agent outputs
    diff_result: DiffResult
    test_plan: TestPlan
    test_artifacts: list[GeneratedTestArtifact]
    generation_stats: dict[str, Any]
    validation_result: ValidationResult
    pr_summary: PullRequestSummary

    # Repair loop
    repair_attempt: int
    failure_logs: str | None

    # Cross-cutting
    error: str | None
    audit_log: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Audit helpers
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    """Immutable record of a single pipeline stage transition."""

    stage: str
    status: str      # "started" | "completed" | "skipped" | "error"
    detail: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )


def _audit(state: PipelineState, stage: str, status: str, detail: str) -> None:
    """Append an audit entry to ``state["audit_log"]``.

    Args:
        state:  The mutable pipeline state.
        stage:  Human-readable stage name (e.g. "diff", "validation[2]").
        status: "started" | "completed" | "skipped" | "error".
        detail: Free-text detail message.
    """
    entry = AuditEntry(stage=stage, status=status, detail=detail)
    state.setdefault("audit_log", [])
    state["audit_log"].append(asdict(entry))  # type: ignore[arg-type]
    logger.info("[orchestrator] [%s] %s — %s", stage, status.upper(), detail)


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Final output returned to the caller after the full pipeline completes."""

    repo_path: str
    repo_id: str
    commit_sha: str
    status: str                  # "completed" | "no_changes" | "failed"
    total_hunks: int
    generated_tests: int
    validation_status: str
    repair_attempts: int
    pr_title: str
    pr_body: str
    audit_log: list[dict[str, Any]]
    error: str | None = None
    finished_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    repo_path: str,
    repo_id: str,
    *,
    pull: bool = True,
    max_repair_attempts: int = DEFAULT_MAX_REPAIR_ATTEMPTS,
) -> PipelineResult:
    """Run the complete autonomous QA pipeline synchronously.

    This is the primary entry-point for Celery tasks, CLI scripts, and any
    context where blocking I/O is acceptable.

    Args:
        repo_path:            Absolute path to the cloned git repository.
        repo_id:              Chroma vector store identifier for this repo.
        pull:                 Whether to perform a ``git pull`` before diffing.
        max_repair_attempts:  Maximum validation → repair cycles before giving up.

    Returns:
        A ``PipelineResult`` summarising the full run.

    Raises:
        Never — all exceptions are captured and reflected in ``result.error``.
    """
    logger.info(
        "[orchestrator] Pipeline start. repo_path=%s repo_id=%s pull=%s",
        repo_path, repo_id, pull,
    )

    state: PipelineState = {
        "repo_path": repo_path,
        "repo_id": repo_id,
        "pull": pull,
        "max_repair_attempts": max_repair_attempts,
        "repair_attempt": 0,
        "failure_logs": None,
        "error": None,
        "audit_log": [],
    }

    # ------------------------------------------------------------------ #
    # Stage 1 — Diff Analysis                                             #
    # ------------------------------------------------------------------ #
    _audit(state, "diff", "started", f"Analysing diff for repo {repo_id}.")
    try:
        state = diff_agent.run(state)  # type: ignore[assignment]
    except Exception as exc:  # noqa: BLE001
        state["error"] = str(exc)

    if state.get("error"):
        _audit(state, "diff", "error", state["error"])
        return _build_result(state, "failed")

    diff_result: DiffResult = state["diff_result"]
    _audit(state, "diff", "completed", f"{len(diff_result.hunks)} hunk(s) found.")

    if not diff_result.has_changes:
        _audit(state, "pipeline", "skipped", "No supported source changes detected.")
        return _build_result(state, "no_changes")

    # ------------------------------------------------------------------ #
    # Stage 2 — Planning                                                  #
    # ------------------------------------------------------------------ #
    _audit(state, "planner", "started", "Building test plan.")
    try:
        state = planner_agent.run(state)  # type: ignore[assignment]
    except Exception as exc:  # noqa: BLE001
        state["error"] = str(exc)

    if state.get("error") or state.get("test_plan") is None:
        _audit(state, "planner", "error", state.get("error", "Unknown planning failure."))
        return _build_result(state, "failed")

    plan: TestPlan = state["test_plan"]
    _audit(state, "planner", "completed", f"{len(plan.targets)} target(s) planned.")

    if plan.is_empty:
        _audit(state, "pipeline", "skipped", "Plan has zero targets.")
        return _build_result(state, "no_changes")

    # ------------------------------------------------------------------ #
    # Stages 3 + 4 — Generate → Validate → Repair loop                  #
    # ------------------------------------------------------------------ #
    final_validation: ValidationResult | None = None

    for attempt in range(max_repair_attempts + 1):
        state["repair_attempt"] = attempt

        # ----- Generation -----
        stage_label = f"generator[{attempt}]"
        _audit(state, stage_label, "started", f"Generating tests (attempt {attempt}).")
        try:
            state = test_generator_agent.run(state)  # type: ignore[assignment]
        except Exception as exc:  # noqa: BLE001
            state["error"] = str(exc)

        if state.get("error"):
            _audit(state, stage_label, "error", state["error"])
            return _build_result(state, "failed")

        _audit(
            state, stage_label, "completed",
            f"{state['generation_stats'].get('generated', 0)} file(s) generated.",
        )

        # ----- Validation -----
        val_label = f"validation[{attempt}]"
        _audit(state, val_label, "started", "Running test suite.")
        try:
            state = validation_agent.run(state)  # type: ignore[assignment]
        except Exception as exc:  # noqa: BLE001
            state["error"] = str(exc)

        if state.get("error"):
            _audit(state, val_label, "error", state["error"])
            return _build_result(state, "failed")

        vr: ValidationResult = state["validation_result"]
        final_validation = vr
        _audit(
            state, val_label, "completed",
            f"status={vr.status} passed={vr.passed_files}/{vr.total_files}.",
        )

        if vr.passed:
            _audit(state, "pipeline", "completed", "All tests passed validation.")
            break

        if attempt >= max_repair_attempts:
            _audit(
                state, "pipeline", "failed",
                f"Max repair attempts ({max_repair_attempts}) exhausted.",
            )
            break

        # Prepare next repair cycle
        _audit(
            state, f"repair[{attempt}]", "started",
            f"Tests failed — queuing repair cycle {attempt + 1}/{max_repair_attempts}.",
        )

    # ------------------------------------------------------------------ #
    # Stage 5 — PR Summary                                               #
    # ------------------------------------------------------------------ #
    _audit(state, "pr_agent", "started", "Building PR summary.")
    try:
        state = pr_agent.run(state)  # type: ignore[assignment]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[orchestrator] PR agent non-fatal failure: %s", exc)

    _audit(state, "pr_agent", "completed", "PR summary ready.")

    overall_status = (
        "completed" if (final_validation and final_validation.passed) else "failed"
    )
    return _build_result(state, overall_status)


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _build_result(state: PipelineState, status: str) -> PipelineResult:
    """Construct a ``PipelineResult`` from the current pipeline state.

    Args:
        state:  The final pipeline state.
        status: Top-level outcome ("completed" | "no_changes" | "failed").

    Returns:
        Populated ``PipelineResult``.
    """
    diff_result: DiffResult | None = state.get("diff_result")
    plan: TestPlan | None = state.get("test_plan")
    gen_stats: dict = state.get("generation_stats") or {}
    vr: ValidationResult | None = state.get("validation_result")
    pr: PullRequestSummary | None = state.get("pr_summary")

    return PipelineResult(
        repo_path=state.get("repo_path", ""),
        repo_id=state.get("repo_id", ""),
        commit_sha=diff_result.commit_sha if diff_result else "unknown",
        status=status,
        total_hunks=len(diff_result.hunks) if diff_result else 0,
        generated_tests=gen_stats.get("generated", 0),
        validation_status=vr.status if vr else "not_run",
        repair_attempts=state.get("repair_attempt", 0),
        pr_title=pr.title if pr else "",
        pr_body=pr.body if pr else "",
        audit_log=state.get("audit_log", []),
        error=state.get("error"),
    )


# ---------------------------------------------------------------------------
# Async wrapper (FastAPI / BackgroundTasks compatible)
# ---------------------------------------------------------------------------

async def run_pipeline_async(
    repo_path: str,
    repo_id: str,
    *,
    pull: bool = True,
    max_repair_attempts: int = DEFAULT_MAX_REPAIR_ATTEMPTS,
) -> PipelineResult:
    """Async wrapper around ``run_pipeline``.

    The synchronous pipeline is executed in a thread pool executor to avoid
    blocking the event loop during CPU/IO-heavy stages (git ops, ChromaDB
    writes, subprocess test execution).

    Args:
        repo_path:            Absolute path to the cloned git repository.
        repo_id:              Chroma vector store identifier for this repo.
        pull:                 Whether to perform ``git pull`` before diffing.
        max_repair_attempts:  Maximum validation → repair cycles.

    Returns:
        A ``PipelineResult`` from the underlying synchronous pipeline.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: run_pipeline(
            repo_path,
            repo_id,
            pull=pull,
            max_repair_attempts=max_repair_attempts,
        ),
    )
