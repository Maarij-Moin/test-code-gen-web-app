"""
Diff Agent — wraps the diff pipeline into a typed, LangGraph-compatible node.

Responsibilities
----------------
- Pull the latest changes from the remote (git pull).
- Detect which source files changed in the last commit.
- Parse each changed hunk into old/new code with function-level granularity.
- Return a structured ``DiffResult`` that the orchestrator passes downstream.

LangGraph integration
---------------------
``run`` is a synchronous function that accepts and returns a plain dict (the
graph ``State``).  Call it inside a LangGraph ``StateGraph`` node directly::

    graph.add_node("diff", diff_agent.run)

Isolation guarantee
-------------------
This agent does NOT touch the vectorstore, generate prompts, or validate tests.
It only concerns itself with git operations and diff parsing.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import git

from app.services.diff_service import get_changed_files, get_function_diff
from app.services.language_config import EXTENSION_MAP, GENERIC_EXTENSION_MAP

logger = logging.getLogger(__name__)

# All file extensions this platform understands.
_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    EXTENSION_MAP.keys() | GENERIC_EXTENSION_MAP.keys()
)


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class DiffHunk:
    """A single changed code unit (function or top-level block)."""

    file: str           # Path relative to repo root.
    function_name: str  # Best-guess name from the hunk header.
    old_code: str       # Lines removed in this hunk (joined with newlines).
    new_code: str       # Lines added in this hunk (joined with newlines).
    language: str       # Resolved language name (e.g. "Python", "Go").
    framework: str      # Resolved test framework (e.g. "pytest", "Jest").
    abs_file_path: str  # Absolute path on disk.


@dataclass
class DiffResult:
    """Aggregated output from the diff agent for one pipeline run."""

    repo_path: str
    repo_id: str
    commit_sha: str                  # HEAD commit hash at analysis time.
    total_changed_files: int
    supported_changed_files: int
    hunks: list[DiffHunk] = field(default_factory=list)
    error: str | None = None
    analysed_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )

    @property
    def has_changes(self) -> bool:
        return len(self.hunks) > 0

    @property
    def failed(self) -> bool:
        return self.error is not None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_lang_info(rel_path: str) -> dict[str, str]:
    """Return {name, framework} for *rel_path* based on its extension.

    Falls back to {"name": "Unknown", "framework": "pytest"} for unmapped
    extensions so that downstream agents always have a non-empty value.
    """
    ext = os.path.splitext(rel_path)[1].lower()
    info = EXTENSION_MAP.get(ext) or GENERIC_EXTENSION_MAP.get(ext, {})
    return {
        "name": info.get("name", "Unknown"),
        "framework": info.get("framework", "pytest"),
    }


def _get_head_sha(repo_path: str) -> str:
    """Return the current HEAD commit hash, or 'unknown' on failure."""
    try:
        return git.Repo(repo_path).head.commit.hexsha
    except Exception:  # noqa: BLE001
        return "unknown"


def _pull_latest(repo_path: str) -> None:
    """Attempt a ``git pull`` on the origin remote.

    Silently skips if the repo has no remotes (local-only), if the working
    tree is dirty, or if any git error occurs — those cases are common in CI
    environments and should not abort the pipeline.
    """
    try:
        repo = git.Repo(repo_path)
        if not repo.remotes:
            logger.debug("[diff_agent] No remotes configured — skipping pull.")
            return
        repo.remotes.origin.pull()
        logger.info("[diff_agent] git pull complete for %s", repo_path)
    except git.GitCommandError as exc:
        logger.warning("[diff_agent] git pull skipped (non-fatal): %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[diff_agent] Unexpected pull error (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse_diff(repo_path: str, repo_id: str, *, pull: bool = True) -> DiffResult:
    """Analyse the latest commit diff for *repo_path*.

    Args:
        repo_path: Absolute local path to the cloned git repository.
        repo_id:   Stable vector repo identifier (from ``make_repo_id``).
        pull:      Whether to attempt a ``git pull`` before diffing.
                   Set to False in tests or when the caller already pulled.

    Returns:
        A ``DiffResult`` instance.  Check ``.failed`` before proceeding.

    Raises:
        Never — all exceptions are captured and returned via ``result.error``.
    """
    logger.info(
        "[diff_agent] Starting diff analysis. repo_path=%s repo_id=%s",
        repo_path, repo_id,
    )

    # Optional pull (non-fatal on failure)
    if pull:
        _pull_latest(repo_path)

    commit_sha = _get_head_sha(repo_path)
    audit: dict[str, Any] = {
        "repo_path": repo_path,
        "repo_id": repo_id,
        "commit_sha": commit_sha,
        "pull": pull,
    }

    # ------------------------------------------------------------------ #
    # Step 1: Identify changed files                                       #
    # ------------------------------------------------------------------ #
    try:
        all_changed = get_changed_files(repo_path)
    except Exception as exc:  # noqa: BLE001
        msg = f"Failed to list changed files: {exc}"
        logger.error("[diff_agent] %s", msg, exc_info=True)
        return DiffResult(
            repo_path=repo_path,
            repo_id=repo_id,
            commit_sha=commit_sha,
            total_changed_files=0,
            supported_changed_files=0,
            error=msg,
        )

    supported = [
        f for f in all_changed
        if os.path.splitext(f)[1].lower() in _SUPPORTED_EXTENSIONS
    ]

    logger.info(
        "[diff_agent] %d file(s) changed — %d with supported extension(s).",
        len(all_changed), len(supported),
    )

    if not supported:
        return DiffResult(
            repo_path=repo_path,
            repo_id=repo_id,
            commit_sha=commit_sha,
            total_changed_files=len(all_changed),
            supported_changed_files=0,
        )

    # ------------------------------------------------------------------ #
    # Step 2: Parse hunks for each supported file                         #
    # ------------------------------------------------------------------ #
    hunks: list[DiffHunk] = []

    for rel_path in supported:
        try:
            raw_hunks = get_function_diff(repo_path, rel_path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[diff_agent] Hunk parse failed for %s: %s", rel_path, exc)
            continue

        if not raw_hunks:
            logger.debug("[diff_agent] No hunks in %s — skipping.", rel_path)
            continue

        lang_info = _resolve_lang_info(rel_path)
        abs_path = os.path.join(repo_path, rel_path)

        for h in raw_hunks:
            hunks.append(
                DiffHunk(
                    file=rel_path,
                    function_name=h.get("function_name", "<unknown>"),
                    old_code=h.get("old_code", ""),
                    new_code=h.get("new_code", ""),
                    language=lang_info["name"],
                    framework=lang_info["framework"],
                    abs_file_path=abs_path,
                )
            )

    logger.info(
        "[diff_agent] Analysis complete. %d hunk(s) across %d file(s).",
        len(hunks), len(supported),
    )

    return DiffResult(
        repo_path=repo_path,
        repo_id=repo_id,
        commit_sha=commit_sha,
        total_changed_files=len(all_changed),
        supported_changed_files=len(supported),
        hunks=hunks,
    )


# ---------------------------------------------------------------------------
# LangGraph node adapter
# ---------------------------------------------------------------------------

def run(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node entry-point.

    Reads from state keys:
        ``repo_path`` (str)  — required.
        ``repo_id``   (str)  — required.
        ``pull``      (bool) — optional, defaults to True.

    Writes to state keys:
        ``diff_result``  (DiffResult) — the analysis output.
        ``error``        (str | None) — non-None signals pipeline abort.

    Args:
        state: Mutable LangGraph state dict.

    Returns:
        Updated state dict with ``diff_result`` and ``error`` keys set.
    """
    repo_path: str = state["repo_path"]
    repo_id: str = state["repo_id"]
    pull: bool = state.get("pull", True)

    result = analyse_diff(repo_path, repo_id, pull=pull)

    state["diff_result"] = result
    state["error"] = result.error

    if result.error:
        logger.error("[diff_agent] node → error: %s", result.error)
    elif not result.has_changes:
        logger.info("[diff_agent] node → no supported changes; pipeline will short-circuit.")

    return state
