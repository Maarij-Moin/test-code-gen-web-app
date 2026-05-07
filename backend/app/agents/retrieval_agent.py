"""Retrieval agent for fetching related code/test context."""

from __future__ import annotations

import logging
from typing import Any

from app.services.embedding_service import load_vectorstore, retrieve_related_chunks


logger = logging.getLogger(__name__)


def retrieve_context(
    repo_id: str,
    query: str,
    k_code: int = 5,
    k_tests: int = 3,
    language: str | None = None,
) -> dict[str, list[Any]]:
    """Retrieve related implementation and test chunks.

    Args:
        repo_id: Repository ID used to load vectorstore.
        query: Query string built from diff information.
        k_code: Number of code chunks to retrieve.
        k_tests: Number of test chunks to retrieve.
        language: Optional language filter.

    Returns:
        Dictionary containing code_chunks and test_chunks.
    """

    logger.info("[retrieval_agent] repo_id=%s query_len=%d", repo_id, len(query))
    vectorstore = load_vectorstore(repo_id)
    code_chunks, test_chunks = retrieve_related_chunks(
        query=query,
        vectorstore=vectorstore,
        k_code=k_code,
        k_tests=k_tests,
        meta_language_if_known=language,
    )
    return {"code_chunks": code_chunks, "test_chunks": test_chunks}
