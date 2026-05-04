import os
import re
import git


def get_changed_files(repo_path: str) -> list[str]:
    """Return a list of file paths (relative to repo root) changed in the last commit."""
    repo = git.Repo(repo_path)
    diff = repo.git.diff("HEAD~1", name_only=True)
    return [f for f in diff.split("\n") if f.strip()]


def get_function_diff(repo_path: str, file_path: str) -> list[dict]:
    """Parse `git diff HEAD~1` for *file_path* and extract changed functions/methods.

    For each changed hunk, returns a dict with:
        - "function_name": best-guess name from the hunk header (or "<unknown>")
        - "old_code":      lines removed  (prefixed with '-' in the diff)
        - "new_code":      lines added    (prefixed with '+' in the diff)
        - "file_path":     the file that changed

    The -U0 flag suppresses context lines so every hunk is a clean before/after.
    """
    repo = git.Repo(repo_path)

    try:
        raw_diff = repo.git.diff("HEAD~1", "HEAD", "--", file_path, unified=0)
    except git.GitCommandError as e:
        print(f"[get_function_diff] git error for {file_path}: {e}")
        return []

    if not raw_diff.strip():
        return []

    hunks: list[dict] = []
    current_hunk: dict | None = None

    # Regex to capture the optional function/method name from the hunk header:
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
            continue  # skip file headers (---, +++)

        if line.startswith("-") and not line.startswith("---"):
            current_hunk["old_code"].append(line[1:])  # strip leading '-'
        elif line.startswith("+") and not line.startswith("+++"):
            current_hunk["new_code"].append(line[1:])  # strip leading '+'

    if current_hunk:
        hunks.append(current_hunk)

    # Convert line lists to strings
    for h in hunks:
        h["old_code"] = "\n".join(h["old_code"])
        h["new_code"] = "\n".join(h["new_code"])

    return hunks