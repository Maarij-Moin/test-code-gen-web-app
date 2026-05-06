import logging
import os

import git

logger = logging.getLogger(__name__)

BASE_DIR = "repo"


def clone_repo(repo_url: str) -> str:
    """Clone *repo_url* into ``<BASE_DIR>/<repo_name>/`` and return the local path.

    Raises:
        ValueError:       If *repo_url* is empty or does not look like a valid Git URL.
        FileExistsError:  (never raised — already-cloned repos are silently reused.)
        RuntimeError:     If the ``git clone`` operation fails for any reason
                          (bad credentials, network error, repo not found, etc.).
    """
    if not repo_url or not repo_url.strip():
        raise ValueError("repo_url must not be empty.")

    # Sanity-check: Git URLs must contain at least one slash after the scheme
    # and must not be a bare filename.
    stripped = repo_url.strip()
    if not (
        stripped.startswith("http://")
        or stripped.startswith("https://")
        or stripped.startswith("git@")
        or stripped.startswith("ssh://")
        or os.path.isabs(stripped)          # allow local bare repos
    ):
        raise ValueError(
            f"Invalid repo URL: '{repo_url}'. "
            "Expected an http(s)://, git@, ssh://, or absolute-path URL."
        )

    repo_name = stripped.rstrip("/").split("/")[-1].replace(".git", "")
    if not repo_name:
        raise ValueError(
            f"Cannot derive a repository name from URL: '{repo_url}'."
        )

    repo_path = os.path.join(BASE_DIR, repo_name)

    os.makedirs(BASE_DIR, exist_ok=True)

    if os.path.exists(repo_path):
        logger.info(
            "Repository '%s' already cloned at '%s' — reusing existing clone.",
            repo_name, repo_path,
        )
        return repo_path

    logger.info("Cloning '%s' → '%s' …", repo_url, repo_path)
    try:
        git.Repo.clone_from(repo_url, repo_path)
    except git.GitCommandError as exc:
        # Clean up partial clone directory so the next attempt starts fresh.
        import shutil
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path, ignore_errors=True)
        raise RuntimeError(
            f"Failed to clone repository '{repo_url}': {exc.stderr.strip()}"
        ) from exc

    logger.info("Clone complete: '%s'", repo_path)
    return repo_path