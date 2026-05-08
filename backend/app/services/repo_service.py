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


def pull_repo(repo_path: str) -> None:
    """Pull the latest changes for an existing local repository.

    Args:
        repo_path: Absolute or relative path to the repo root.

    Raises:
        RuntimeError: If the repo is invalid or git pull fails.
    """

    if not repo_path or not os.path.exists(repo_path):
        raise RuntimeError(f"Repository path does not exist: '{repo_path}'.")

    try:
        repo = git.Repo(repo_path)
        repo.remotes.origin.pull()
        logger.info("Pulled latest changes for '%s'.", repo_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to pull repository '{repo_path}': {exc}") from exc


def commit_and_push_tests(repo_path: str, branch_name: str, commit_message: str) -> None:
    """Commit auto_tests/ directory and push to a new remote branch.
    
    Uses GITHUB_TOKEN for authentication if available.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("GITHUB_TOKEN not found, skipping push.")
        return

    try:
        repo = git.Repo(repo_path)
        
        # Create and checkout new branch
        if branch_name in [b.name for b in repo.branches]:
            repo.git.checkout(branch_name)
        else:
            repo.git.checkout('-b', branch_name)
            
        # Add auto_tests directory
        test_dir = os.path.join(repo_path, "auto_tests")
        if not os.path.exists(test_dir):
            logger.info("No auto_tests directory found to commit.")
            return
            
        repo.git.add("auto_tests/")
        
        # Check if there are changes to commit
        if not repo.is_dirty() and not repo.untracked_files:
            logger.info("No changes to commit in auto_tests/")
            return
            
        repo.git.commit('-m', commit_message)
        
        # Update remote URL to include token
        origin = repo.remotes.origin
        remote_url = origin.url
        if remote_url.startswith("https://") and "@" not in remote_url:
            auth_url = remote_url.replace("https://", f"https://x-access-token:{token}@")
            origin.set_url(auth_url)
            
        repo.git.push('--set-upstream', 'origin', branch_name)
        logger.info("Pushed tests to branch '%s'", branch_name)
        
        # Restore URL
        origin.set_url(remote_url)
        
    except Exception as exc:
        raise RuntimeError(f"Failed to commit and push tests: {exc}") from exc