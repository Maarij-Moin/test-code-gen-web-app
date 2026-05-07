"""
Planner Agent — converts raw diff hunks into a prioritised, typed test plan.

Responsibilities
----------------
- Accept a ``DiffResult`` from the diff agent.
- Classify each hunk by intent (regression, new-behaviour, edge-case).
- Assign a priority score based on heuristics (function name patterns,
  code complexity proxies, file criticality).
- Return a ``TestPlan`` consumed by the ``test_generator_agent``.

LangGraph integration
---------------------
``run(state)`` reads ``diff_result`` from the graph state and writes
``test_plan`` back.  The function is safe to use as a synchronous node::

    graph.add_node("planner", planner_agent.run)

Design notes
------------
- Priority heuristics are intentionally simple so they work without an LLM
  call.  They can be enriched later by plugging in an LLM-based classifier.
- Every ``TestTarget`` carries a ``query`` field — the exact search string the
  retrieval agent will use to fetch related context from ChromaDB.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.agents.diff_agent import DiffHunk, DiffResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Priority rules (lightweight heuristics — no LLM needed)
# ---------------------------------------------------------------------------

# Pattern → priority boost
_CRITICAL_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"auth|login|token|password|secret", re.I), 3),
    (re.compile(r"pay|charge|billing|invoice|stripe", re.I), 3),
    (re.compile(r"delete|remove|drop|purge|truncate", re.I), 2),
    (re.compile(r"migrate|rollback|upgrade", re.I), 2),
    (re.compile(r"api|endpoint|route|handler", re.I), 1),
]

# Base priority for any changed code
_BASE_PRIORITY = 5


def _compute_priority(hunk: DiffHunk) -> int:
    """Score a hunk from 1 (lowest) to 10 (highest) using pattern heuristics.

    Args:
        hunk: The diff hunk to score.

    Returns:
        Integer priority score in the range [1, 10].
    """
    score = _BASE_PRIORITY
    text = f"{hunk.function_name} {hunk.file}"
    for pattern, boost in _CRITICAL_PATTERNS:
        if pattern.search(text):
            score += boost
    return min(score, 10)


def _classify_intent(hunk: DiffHunk) -> str:
    """Assign a testing intent label to a hunk.

    Intents:
        ``new_behaviour``   — no old code; something was added.
        ``regression``      — existing code was modified.
        ``deletion``        — code was removed; tests may need removal too.

    Args:
        hunk: The diff hunk to classify.

    Returns:
        Intent label string.
    """
    if not hunk.old_code.strip() and hunk.new_code.strip():
        return "new_behaviour"
    if hunk.old_code.strip() and not hunk.new_code.strip():
        return "deletion"
    return "regression"


def _build_query(hunk: DiffHunk) -> str:
    """Build a ChromaDB retrieval query from the hunk.

    The query combines the function name with the first 200 characters of the
    new code so that semantic search finds the most relevant context.

    Args:
        hunk: The diff hunk to build a query for.

    Returns:
        Query string for the retrieval agent.
    """
    code_snippet = hunk.new_code[:200].strip() if hunk.new_code else hunk.old_code[:200].strip()
    combined = f"{hunk.function_name} {code_snippet}".strip()
    # Normalise whitespace
    return re.sub(r"\s+", " ", combined)


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class TestTarget:
    """Describes a single function/class to be tested."""

    file: str               # Path relative to repo root.
    abs_file_path: str      # Absolute path for test generation.
    function_name: str      # Hunk-level identifier.
    language: str           # e.g. "Python"
    framework: str          # e.g. "pytest"
    intent: str             # "regression" | "new_behaviour" | "deletion"
    priority: int           # 1 (lowest) → 10 (highest)
    query: str              # ChromaDB retrieval query.
    old_code: str           # Lines removed.
    new_code: str           # Lines added.


@dataclass
class TestPlan:
    """Structured plan produced by the planner agent."""

    repo_path: str
    repo_id: str
    commit_sha: str
    strategy: str
    rationale: str
    targets: list[TestTarget] = field(default_factory=list)
    planned_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )

    @property
    def is_empty(self) -> bool:
        return len(self.targets) == 0

    @property
    def high_priority_targets(self) -> list[TestTarget]:
        return [t for t in self.targets if t.priority >= 8]

    def sorted_targets(self) -> list[TestTarget]:
        """Return targets ordered highest → lowest priority."""
        return sorted(self.targets, key=lambda t: t.priority, reverse=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_plan(diff_result: DiffResult) -> TestPlan:
    """Convert a ``DiffResult`` into a prioritised ``TestPlan``.

    Each hunk in the diff becomes exactly one ``TestTarget``.  Targets are
    sorted highest-priority first so the generator agent works on the most
    critical changes before any budget/timeout is exhausted.

    Args:
        diff_result: Output from ``diff_agent.analyse_diff``.

    Returns:
        A populated ``TestPlan``.  May have an empty ``targets`` list if the
        diff contained no hunks (e.g. only non-source files changed).
    """
    logger.info(
        "[planner_agent] Building plan. repo_id=%s hunks=%d",
        diff_result.repo_id, len(diff_result.hunks),
    )

    targets: list[TestTarget] = []

    for hunk in diff_result.hunks:
        intent = _classify_intent(hunk)
        priority = _compute_priority(hunk)
        query = _build_query(hunk)

        target = TestTarget(
            file=hunk.file,
            abs_file_path=hunk.abs_file_path,
            function_name=hunk.function_name,
            language=hunk.language,
            framework=hunk.framework,
            intent=intent,
            priority=priority,
            query=query,
            old_code=hunk.old_code,
            new_code=hunk.new_code,
        )
        targets.append(target)
        logger.debug(
            "[planner_agent] Target: file=%s fn=%s intent=%s priority=%d",
            hunk.file, hunk.function_name, intent, priority,
        )

    # Sort highest priority first so the generator tackles critical targets first.
    targets.sort(key=lambda t: t.priority, reverse=True)

    strategy = (
        "Generate regression-focused tests for all changed functions, "
        "prioritising security-sensitive and data-destructive operations."
    )
    rationale = (
        f"{len(targets)} test target(s) identified from {diff_result.supported_changed_files} "
        f"changed file(s) at commit {diff_result.commit_sha[:8]}."
    )

    plan = TestPlan(
        repo_path=diff_result.repo_path,
        repo_id=diff_result.repo_id,
        commit_sha=diff_result.commit_sha,
        strategy=strategy,
        rationale=rationale,
        targets=targets,
    )

    logger.info(
        "[planner_agent] Plan built: %d target(s), %d high-priority.",
        len(targets), len(plan.high_priority_targets),
    )
    return plan


# ---------------------------------------------------------------------------
# LangGraph node adapter
# ---------------------------------------------------------------------------

def run(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node entry-point for the planner.

    Reads from state:
        ``diff_result`` (DiffResult) — required.

    Writes to state:
        ``test_plan`` (TestPlan) — the structured plan.
        ``error``     (str | None) — set if planning fails.

    Args:
        state: Mutable LangGraph state dict.

    Returns:
        Updated state dict.
    """
    diff_result: DiffResult = state["diff_result"]

    try:
        plan = build_plan(diff_result)
        state["test_plan"] = plan
        # Preserve any upstream error; only clear if planning itself is fine.
        if "error" not in state:
            state["error"] = None
    except Exception as exc:  # noqa: BLE001
        msg = f"[planner_agent] Planning failed: {exc}"
        logger.exception(msg)
        state["test_plan"] = None
        state["error"] = msg

    return state
