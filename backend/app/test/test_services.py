"""Service layer for AI-driven test generation workflows."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.services.diff_pipeline_service import run_diff_pipeline
from app.services.indexing_service import update_vectorstore
from app.services.vectorstore_service import load_vectorstore


logger = logging.getLogger(__name__)


def validate_repo_exists(repo_path: str) -> Path:
    """Ensure the repository path exists and is a directory.

    Args:
        repo_path: Path to the repository root.

    Returns:
        Resolved Path instance.

    Raises:
        ValueError: If repo_path is empty.
        FileNotFoundError: If the path does not exist.
        NotADirectoryError: If the path is not a directory.
    """

    if not repo_path or not repo_path.strip():
        raise ValueError("repo_path must not be empty.")

    path = Path(repo_path)
    if not path.exists():
        raise FileNotFoundError(f"Repository path not found: '{repo_path}'.")
    if not path.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: '{repo_path}'.")

    return path.resolve()


def generate_test_prompts(repo_path: str, repo_id: str) -> list[dict[str, Any]]:
    """Run the diff pipeline and return structured prompt results.

    Args:
        repo_path: Repository root path.
        repo_id: Repository ID used to load the vectorstore.

    Returns:
        List of prompt dictionaries per diff hunk.
    """

    validate_repo_exists(repo_path)
    logger.info("Generating test prompts for repo_id=%s", repo_id)
    return run_diff_pipeline(repo_path=repo_path, repo_id=repo_id)


def query_test_chunks(repo_id: str, query: str, k: int = 5) -> list[Any]:
    """Retrieve only test-related chunks from ChromaDB.

    Args:
        repo_id: Repository ID to query.
        query: Search query string.
        k: Number of results to return.

    Returns:
        List of test-related LangChain Document objects.
    """

    logger.info("Querying test chunks for repo_id=%s", repo_id)
    vectorstore = load_vectorstore(repo_id)
    return vectorstore.similarity_search(query, k=k, filter={"is_test_file": True})


def format_test_generation_response(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Normalize test generation responses for API output."""

    total_prompts = len(results)
    return {
        "success": True,
        "total_prompts": total_prompts,
        "results": results,
    }


def summarize_generated_tests(results: list[dict[str, Any]]) -> dict[str, int]:
    """Return summary statistics for generated test prompts.

    Args:
        results: Prompt generation results from the diff pipeline.

    Returns:
        Dictionary containing summary statistics.
    """

    changed_files = {item.get("file") for item in results if item.get("file")}
    changed_functions = {
        item.get("function_name")
        for item in results
        if item.get("function_name")
    }

    return {
        "total_prompts": len(results),
        "changed_files": len(changed_files),
        "functions_changed": len(changed_functions),
    }


def trigger_incremental_update(repo_path: str, repo_id: str) -> int:
    """Trigger an incremental vectorstore update and return added chunk count."""

    validate_repo_exists(repo_path)
    _, updated_chunks = update_vectorstore(repo_path=repo_path, repo_id=repo_id)
    return updated_chunks
