"""
AI agent orchestration package.

Public agents (each exposes a ``run(state: dict) -> dict`` LangGraph node)
and their typed data contracts:

    diff_agent              → DiffResult
    planner_agent           → TestPlan
    test_generator_agent    → list[GeneratedTestArtifact]
    validation_agent        → ValidationResult
    pr_agent                → PullRequestSummary

The ``retrieval_agent`` module handles vectorstore context fetching and is
imported by ``test_generator_agent``; it is not a LangGraph node itself.
"""

from app.agents import (
    diff_agent,
    planner_agent,
    test_generator_agent,
    validation_agent,
    pr_agent,
)

__all__ = [
    "diff_agent",
    "planner_agent",
    "test_generator_agent",
    "validation_agent",
    "pr_agent",
]
