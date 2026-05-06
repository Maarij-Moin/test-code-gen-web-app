import logging
import os
import re

import git

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_repo(repo_path: str) -> git.Repo:
    """Open the Git repo at *repo_path* or raise a descriptive error.

    Raises:
        ValueError:       *repo_path* is empty or ``None``.
        FileNotFoundError: The path does not exist on disk.
        RuntimeError:     The path exists but is not a Git repository.
    """
    if not repo_path or not repo_path.strip():
        raise ValueError("repo_path must not be empty.")

    if not os.path.exists(repo_path):
        raise FileNotFoundError(
            f"Repository path not found on disk: '{repo_path}'. "
            "Clone the repository first via the /repos/clone-and-index endpoint."
        )

    try:
        return git.Repo(repo_path)
    except git.InvalidGitRepositoryError:
        raise RuntimeError(
            f"The path '{repo_path}' exists but is not a valid Git repository. "
            "Make sure you are pointing at the repository root (where .git/ lives)."
        )
    except git.NoSuchPathError:
        # Raised by GitPython when the path disappeared between our os.path.exists
        # check and Repo() initialisation (race condition).
        raise FileNotFoundError(
            f"Repository path disappeared unexpectedly: '{repo_path}'."
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_changed_files(repo_path: str) -> list[str]:
    """Return file paths (relative to the repo root) changed in the last commit.

    Raises:
        ValueError:       *repo_path* is empty.
        FileNotFoundError: Path not found on disk.
        RuntimeError:     Path is not a Git repository, or there is no previous
                          commit to diff against (e.g. a repo with only one commit).
    """
    repo = _validate_repo(repo_path)

    try:
        raw = repo.git.diff("HEAD~1", name_only=True)
    except git.GitCommandError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        raise RuntimeError(
            f"Could not compute git diff for '{repo_path}'. "
            "This may happen if the repository has only one commit "
            f"(no HEAD~1 exists). Git error: {stderr}"
        ) from exc

    files = [f for f in raw.split("\n") if f.strip()]

    if not files:
        logger.info(
            "[get_changed_files] No files changed between HEAD~1 and HEAD in '%s'.",
            repo_path,
        )

    logger.debug(
        "[get_changed_files] %d changed file(s) detected in '%s'.",
        len(files), repo_path,
    )
    return files


def get_function_diff(repo_path: str, file_path: str) -> list[dict]:
    """Parse ``git diff HEAD~1`` for *file_path* and extract changed hunks.

    For each hunk, returns a dict with:
        - ``function_name``: best-guess name from the hunk header (``"<unknown>"`` if absent)
        - ``old_code``:      lines removed  (prefixed with ``-`` in the diff)
        - ``new_code``:      lines added    (prefixed with ``+`` in the diff)
        - ``file_path``:     the file that changed

    The ``-U0`` flag suppresses context lines so every hunk is a clean before/after.

    Raises:
        ValueError:       *repo_path* or *file_path* is empty.
        FileNotFoundError: *repo_path* does not exist on disk.
        RuntimeError:     *repo_path* is not a valid Git repository.
    """
    if not file_path or not file_path.strip():
        raise ValueError("file_path must not be empty.")

    repo = _validate_repo(repo_path)

    try:
        raw_diff = repo.git.diff("HEAD~1", "HEAD", "--", file_path, unified=0)
    except git.GitCommandError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        logger.warning(
            "[get_function_diff] git diff failed for '%s' in '%s': %s",
            file_path, repo_path, stderr,
        )
        return []

    if not raw_diff.strip():
        logger.debug(
            "[get_function_diff] Empty diff for '%s' — file may be unchanged or binary.",
            file_path,
        )
        return []

    # ------------------------------------------------------------------ #
    # Parse hunks                                                          #
    # ------------------------------------------------------------------ #
    hunks: list[dict] = []
    current_hunk: dict | None = None

    # Captures the optional function/method name in the hunk header:
    # @@ -L,N +L,N @@ <optional function context>
    HUNK_HEADER = re.compile(r'^@@ -[\d,]+ \+[\d,]+ @@\s*(.*)')

    for line in raw_diff.splitlines():
        m = HUNK_HEADER.match(line)
        if m:
            if current_hunk:
                hunks.append(current_hunk)
            func_name = m.group(1).strip() or "<unknown>"
            current_hunk = {
                "function_name": func_name,
                "old_code": [],
                "new_code": [],
                "file_path": file_path,
            }
            continue

        if current_hunk is None:
            continue  # skip file header lines (---, +++)

        if line.startswith("-") and not line.startswith("---"):
            current_hunk["old_code"].append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            current_hunk["new_code"].append(line[1:])

    if current_hunk:
        hunks.append(current_hunk)

    # Convert line lists to strings
    for h in hunks:
        h["old_code"] = "\n".join(h["old_code"])
        h["new_code"] = "\n".join(h["new_code"])

    logger.debug(
        "[get_function_diff] %d hunk(s) parsed from '%s'.",
        len(hunks), file_path,
    )
    return hunks