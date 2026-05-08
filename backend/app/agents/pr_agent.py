"""
PR Agent — builds a structured pull-request summary from pipeline results.

Responsibilities
----------------
- Accept the fully populated pipeline state (plan, artifacts, validation).
- Produce a ``PullRequestSummary`` with a Markdown-formatted body suitable
  for posting to GitHub via the REST API.
- Enumerate every generated test file, its target function, and the
  validation outcome so reviewers have a full audit trail in the PR.

GitHub API integration
----------------------
The ``post_to_github`` helper is provided for direct GitHub REST calls.
It requires ``GITHUB_TOKEN`` in the environment and the repo's ``owner/name``
slug.  Set those before calling; the helper is intentionally kept separate
from the summary builder so the builder can be tested in isolation.

LangGraph integration
---------------------
``run(state)`` is the node entry-point::

    graph.add_node("pr_agent", pr_agent.run)

Reads:
    ``test_plan``         (TestPlan)
    ``test_artifacts``    (list[GeneratedTestArtifact])
    ``validation_result`` (ValidationResult)
    ``generation_stats``  (dict)

Writes:
    ``pr_summary``  (PullRequestSummary)
    ``error``       (str | None)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import urllib.request
import urllib.error
import json

from app.agents.planner_agent import TestPlan
from app.agents.test_generator_agent import GeneratedTestArtifact
from app.agents.validation_agent import ValidationResult
from app.services.repo_service import commit_and_push_tests
from app.services.github_service import create_pull_request
import git

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class PullRequestSummary:
    """Structured PR summary produced by this agent."""

    title: str
    body: str
    repo_name: str
    commit_sha: str
    validation_status: str
    total_targets: int
    generated: int
    passed_files: int
    failed_files: int
    repair_attempt: int
    generated_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def _status_badge(status: str) -> str:
    """Return a GitHub-friendly status label.

    Args:
        status: "passed" | "failed" | any other string.

    Returns:
        Emoji-prefixed label string.
    """
    return "✅ Passed" if status == "passed" else "❌ Failed"


def _artifact_table(artifacts: list[GeneratedTestArtifact]) -> str:
    """Render a Markdown table of generated test artifacts.

    Args:
        artifacts: List of generated test artifacts.

    Returns:
        Markdown table string.
    """
    if not artifacts:
        return "_No test files were generated._\n"

    lines = [
        "| File | Function | Language | Intent | Priority | Status |",
        "|------|----------|----------|--------|----------|--------|",
    ]
    for a in artifacts:
        lines.append(
            f"| `{a.target_file}` | `{a.function_name}` | {a.language} "
            f"| {a.intent} | {a.priority} | scaffold |"
        )
    return "\n".join(lines) + "\n"


def build_pr_summary(
    plan: TestPlan,
    artifacts: list[GeneratedTestArtifact],
    validation_result: ValidationResult | None,
    generation_stats: dict[str, Any],
) -> PullRequestSummary:
    """Construct a rich Markdown PR summary from the pipeline results.

    Args:
        plan:              The test plan produced by the planner agent.
        artifacts:         Generated test artifacts.
        validation_result: Validation outcome (may be None on failure).
        generation_stats:  Stats dict from the generator node.

    Returns:
        A ``PullRequestSummary`` ready for display or GitHub API posting.
    """
    repo_name = os.path.basename(plan.repo_path)
    commit_short = plan.commit_sha[:8]
    v_status = validation_result.status if validation_result else "unknown"
    badge = _status_badge(v_status)
    repair = generation_stats.get("repair_attempt", 0)

    title = f"chore(auto-tests): AI-generated tests for {repo_name} @ {commit_short}"

    body_sections: list[str] = [
        f"## 🤖 Autonomous Test Generation Report",
        f"",
        f"**Repository:** `{repo_name}`  ",
        f"**Commit:** `{plan.commit_sha}`  ",
        f"**Strategy:** {plan.strategy}  ",
        f"**Validation:** {badge}  ",
        f"",
        f"---",
        f"",
        f"### 📊 Statistics",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Changed files analysed | {plan.targets.__class__.__name__ and len(set(t.file for t in plan.targets))} |",
        f"| Test targets planned | {len(plan.targets)} |",
        f"| Tests generated | {generation_stats.get('generated', 0)} |",
        f"| Tests skipped | {generation_stats.get('skipped', 0)} |",
        f"| Files passed validation | {validation_result.passed_files if validation_result else 'N/A'} |",
        f"| Files failed validation | {validation_result.failed_files if validation_result else 'N/A'} |",
        f"| Repair attempts | {repair} |",
        f"",
        f"---",
        f"",
        f"### 🧪 Generated Test Files",
        f"",
        _artifact_table(artifacts),
        f"---",
        f"",
        f"### 📋 Plan Rationale",
        f"",
        f"> {plan.rationale}",
        f"",
    ]

    if validation_result and validation_result.failure_logs:
        body_sections += [
            f"---",
            f"",
            f"### ⚠️ Validation Failures",
            f"",
            f"<details>",
            f"<summary>Click to expand failure logs</summary>",
            f"",
            f"```",
            validation_result.failure_logs[:3000],  # Truncate for GitHub body limit
            f"```",
            f"</details>",
            f"",
        ]

    body_sections += [
        f"---",
        f"",
        f"_Generated by the Autonomous AI QA Platform at {datetime.now(tz=timezone.utc).isoformat()}_",
    ]

    body = "\n".join(body_sections)

    summary = PullRequestSummary(
        title=title,
        body=body,
        repo_name=repo_name,
        commit_sha=plan.commit_sha,
        validation_status=v_status,
        total_targets=len(plan.targets),
        generated=generation_stats.get("generated", 0),
        passed_files=validation_result.passed_files if validation_result else 0,
        failed_files=validation_result.failed_files if validation_result else 0,
        repair_attempt=repair,
    )

    logger.info(
        "[pr_agent] PR summary built for %s @ %s. validation=%s",
        repo_name, commit_short, v_status,
    )
    return summary


# ---------------------------------------------------------------------------
# GitHub API helper (optional / side-effectful)
# ---------------------------------------------------------------------------

def post_to_github(
    summary: PullRequestSummary,
    *,
    owner: str,
    repo: str,
    base_branch: str = "main",
    head_branch: str | None = None,
    github_token: str | None = None,
) -> dict[str, Any]:
    """Post a PR to GitHub using the REST API.

    This is an **optional** side-effectful helper.  It is not called by the
    orchestrator automatically — wire it in only when you have a real token
    and want live PR creation.

    Args:
        summary:       The ``PullRequestSummary`` to post.
        owner:         GitHub repository owner (org or user name).
        repo:          GitHub repository name.
        base_branch:   Branch to merge INTO (default: "main").
        head_branch:   Branch containing the generated tests
                       (default: ``auto-tests/{commit_sha[:8]}``).
        github_token:  Personal access token or GitHub App installation token.
                       Falls back to the ``GITHUB_TOKEN`` environment variable.

    Returns:
        Parsed JSON response from the GitHub API.

    Raises:
        RuntimeError: On HTTP errors or missing token.
    """
    token = github_token or os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN is not set. Provide it via the environment or the "
            "github_token parameter."
        )

    head = head_branch or f"auto-tests/{summary.commit_sha[:8]}"

    payload = json.dumps({
        "title": summary.title,
        "body": summary.body,
        "head": head,
        "base": base_branch,
    }).encode("utf-8")

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub PR creation failed (HTTP {exc.code}): {body}"
        ) from exc


# ---------------------------------------------------------------------------
# LangGraph node adapter
# ---------------------------------------------------------------------------

def run(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node entry-point for the PR agent.

    Reads from state:
        ``test_plan``         (TestPlan)
        ``test_artifacts``    (list[GeneratedTestArtifact])
        ``validation_result`` (ValidationResult | None)
        ``generation_stats``  (dict)

    Writes to state:
        ``pr_summary`` (PullRequestSummary)
        ``error``      (str | None)

    Args:
        state: Mutable LangGraph state dict.

    Returns:
        Updated state dict.
    """
    plan: TestPlan = state["test_plan"]
    artifacts: list[GeneratedTestArtifact] = state.get("test_artifacts", [])
    validation_result: ValidationResult | None = state.get("validation_result")
    generation_stats: dict[str, Any] = state.get("generation_stats", {})

    try:
        summary = build_pr_summary(
            plan=plan,
            artifacts=artifacts,
            validation_result=validation_result,
            generation_stats=generation_stats,
        )
        
        # Automatically commit, push, and open PR
        if os.environ.get("GITHUB_TOKEN"):
            branch_name = f"auto-tests/{summary.commit_sha[:8]}"
            repo_path = plan.repo_path
            
            # 1. Commit and push
            commit_and_push_tests(
                repo_path=repo_path,
                branch_name=branch_name,
                commit_message=summary.title
            )
            
            # 2. Create PR
            try:
                local_repo = git.Repo(repo_path)
                remote_url = list(local_repo.remotes.origin.urls)[0]
                
                # Strip auth token from remote_url if present
                if "@" in remote_url and "github.com" in remote_url:
                    remote_url = "https://github.com/" + remote_url.split("github.com/")[1]
                
                create_pull_request(
                    repo_url=remote_url,
                    branch_name=branch_name,
                    title=summary.title,
                    body=summary.body,
                    changed_files=[a.target_file for a in artifacts],
                    commit_message=summary.title
                )
            except Exception as e:
                logger.error(f"[pr_agent] Failed to create GitHub PR: {e}")
                
        state["pr_summary"] = summary
        state.setdefault("error", None)
    except Exception as exc:  # noqa: BLE001
        msg = f"[pr_agent] node failed: {exc}"
        logger.exception(msg)
        state["pr_summary"] = None
        state["error"] = msg

    return state
