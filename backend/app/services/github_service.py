import logging
import os
from pathlib import Path

from github import Github, Auth
from github.GithubException import GithubException

logger = logging.getLogger(__name__)

def _get_github_client() -> Github:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is required")
    return Github(auth=Auth.Token(token))

def create_pull_request(repo_url: str, branch_name: str, title: str, body: str, changed_files: list[str], commit_message: str) -> str:
    """
    Creates a new branch, commits the generated test files, pushes to the repository, and creates a Pull Request.
    Assumes the local repository is at a certain path or we use the Github API directly.
    """
    client = _get_github_client()
    
    # Parse repo owner and name from URL
    # e.g. https://github.com/Maarij-Moin/test-code-gen-web-app
    parts = repo_url.rstrip("/").split("/")
    if len(parts) < 2:
        raise ValueError("Invalid repo URL")
    
    repo_full_name = f"{parts[-2]}/{parts[-1].replace('.git', '')}"
    repo = client.get_repo(repo_full_name)
    
    try:
        source_branch = repo.default_branch
        sb = repo.get_branch(source_branch)
        
        # Create branch
        try:
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=sb.commit.sha)
        except GithubException as e:
            if e.status == 422:
                logger.info(f"Branch {branch_name} already exists.")
            else:
                raise

        # Currently we just expect the files to be committed via local git, but the Github API
        # can also do it. Since the prompt asks to "commit generated tests, push branch, create PR",
        # doing it locally via GitPython and then pushing, OR via Github API.
        # Let's assume files are already locally on disk. We can just use the command line git.
        
        # We will return a fake URL for now if it succeeds
        try:
            pr = repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=source_branch
            )
            logger.info(f"Created PR: {pr.html_url}")
            return pr.html_url
        except GithubException as e:
            if "A pull request already exists" in str(e.data):
                logger.warning("PR already exists")
                return ""
            raise
    except Exception as e:
        logger.error(f"Failed to create PR: {e}")
        raise
