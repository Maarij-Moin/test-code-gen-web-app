"""Planner agent for translating diffs into test requirements."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class TestPlan:
    """Structured plan output for test generation."""

    strategy: str
    targets: list[dict[str, Any]]
    rationale: str


def plan_tests(diff_results: list[dict[str, Any]]) -> TestPlan:
    """Build a lightweight test plan from diff results.

    Args:
        diff_results: List of diff hunk results from the diff pipeline.

    Returns:
        TestPlan containing strategy and targets.
    """

    logger.info("[planner_agent] Planning tests for %d diff hunks", len(diff_results))

    targets: list[dict[str, Any]] = []
    for hunk in diff_results:
        targets.append(
            {
                "file": hunk.get("file"),
                "function_name": hunk.get("function_name"),
                "intent": "regression",
                "priority": "high",
            }
        )

    strategy = "Generate regression-focused tests for changed functions and cover edge cases."
    rationale = "Diff-driven planning based on changed hunks and function context."

    return TestPlan(strategy=strategy, targets=targets, rationale=rationale)
