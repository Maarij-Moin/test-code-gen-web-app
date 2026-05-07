"""Diff-driven orchestration for AI test generation prompts."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional

from app.services.diff_service import get_changed_files, get_function_diff
from app.services.embedding_service import load_vectorstore, retrieve_related_chunks
from app.services.language_config import EXTENSION_MAP, GENERIC_EXTENSION_MAP
from app.services.prompt_service import generate_test_prompt


logger = logging.getLogger(__name__)


def validate_diff_files(changed_files: List[str], supported_extensions: Iterable[str]) -> List[str]:
    """Filter changed files by supported extensions.

    Args:
        changed_files: List of file paths (relative to repo root).
        supported_extensions: Iterable of supported file extensions.

    Returns:
        Filtered list of supported files.
    """

    supported_set = {ext.lower() for ext in supported_extensions}
    supported_files = [
        path
        for path in changed_files
        if path.strip() and os.path.splitext(path)[1].lower() in supported_set
    ]

    logger.debug(
        "Validated %d changed file(s); %d supported.",
        len(changed_files),
        len(supported_files),
    )
    return supported_files


def build_search_query(function_name: str, new_code: str) -> str:
    """Build a semantic retrieval query from function name and new code.

    Args:
        function_name: Name of the function or unit under change.
        new_code: New code snippet from diff.

    Returns:
        Sanitized search query string.
    """

    name_part = (function_name or "").strip()
    code_part = (new_code or "")[:200]
    combined = f"{name_part} {code_part}".strip()
    sanitized = re.sub(r"\s+", " ", combined)

    logger.debug("Built retrieval query: %s", sanitized)
    return sanitized


def _resolve_lang_info(
    extension_maps: Mapping[str, Mapping[str, Any]],
    extension: str,
) -> Dict[str, Any]:
    """Resolve language metadata from extension maps.

    Args:
        extension_maps: Mapping of extension maps.
        extension: File extension including leading dot.

    Returns:
        Language metadata dictionary.
    """

    extension = extension.lower()

    if "primary" in extension_maps or "generic" in extension_maps:
        primary = extension_maps.get("primary", {})
        generic = extension_maps.get("generic", {})
        return dict(primary.get(extension) or generic.get(extension) or {})

    return dict(extension_maps.get(extension) or {})


def extract_metadata_from_chunks(
    code_chunks: Optional[List[Any]],
    hunk: Dict[str, Any],
    rel_path: str,
    repo_path: str,
    extension_maps: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    """Build metadata for prompt generation from retrieved chunks and fallbacks.

    Args:
        code_chunks: Retrieved implementation chunks.
        hunk: Diff hunk dict with function_name and code blocks.
        rel_path: File path relative to repo root.
        repo_path: Repository root path.
        extension_maps: Mapping of extension metadata.

    Returns:
        Metadata dictionary.
    """

    ext = os.path.splitext(rel_path)[1].lower()
    lang_info = _resolve_lang_info(extension_maps, ext)

    base_meta = {
        "language": lang_info.get("name", "Unknown"),
        "test_framework": lang_info.get("framework", "N/A"),
        "file_path": os.path.join(repo_path, rel_path),
        "unit_name": hunk.get("function_name") or "<unknown>",
    }

    if not code_chunks:
        logger.debug("No code chunks available for metadata extraction")
        return base_meta

    top_meta = getattr(code_chunks[0], "metadata", {}) or {}

    merged = {
        "language": top_meta.get("language", base_meta["language"]),
        "test_framework": top_meta.get("test_framework", base_meta["test_framework"]),
        "file_path": top_meta.get("file_path", base_meta["file_path"]),
        "unit_name": base_meta["unit_name"],
    }

    logger.debug("Metadata extracted for %s: %s", rel_path, merged)
    return merged


def process_diff_hunk(
    hunk: Dict[str, Any],
    rel_path: str,
    repo_path: str,
    vectorstore: Any,
    extension_maps: Mapping[str, Mapping[str, Any]],
) -> Dict[str, str]:
    """Process a single changed function/class diff and build the prompt.

    Args:
        hunk: Diff hunk dictionary from get_function_diff().
        rel_path: File path relative to repo root.
        repo_path: Repository root path.
        vectorstore: Loaded vectorstore instance.
        extension_maps: Mapping of extension metadata.

    Returns:
        Structured result with prompt and diff context.
    """

    function_name = hunk.get("function_name") or "<unknown>"
    old_code = hunk.get("old_code") or ""
    new_code = hunk.get("new_code") or ""

    query = build_search_query(function_name, new_code)

    ext = os.path.splitext(rel_path)[1].lower()
    lang_info = _resolve_lang_info(extension_maps, ext)
    language = lang_info.get("name") or None

    code_chunks, test_chunks = retrieve_related_chunks(
        query, vectorstore, meta_language_if_known=language
    )

    metadata = extract_metadata_from_chunks(
        code_chunks=code_chunks,
        hunk=hunk,
        rel_path=rel_path,
        repo_path=repo_path,
        extension_maps=extension_maps,
    )

    prompt = generate_test_prompt(
        old_code=old_code,
        new_code=new_code,
        related_chunks=code_chunks,
        existing_tests=test_chunks,
        metadata=metadata,
    )

    result = {
        "file": rel_path,
        "function_name": function_name,
        "old_code": old_code,
        "new_code": new_code,
        "prompt": prompt,
    }

    logger.info(
        "Processed hunk: file=%s function=%s query_len=%d",
        rel_path,
        function_name,
        len(query),
    )
    return result


def run_diff_pipeline(
    repo_path: str,
    vectorstore: Any = None,
    repo_id: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Orchestrate diff-driven prompt generation pipeline.

    Args:
        repo_path: Path to the git repository root.
        vectorstore: Loaded vectorstore instance.
        repo_id: Repository ID used to load vectorstore when not provided.

    Returns:
        List of prompt generation results.
    """

    if not repo_path or not repo_path.strip():
        raise ValueError("repo_path must not be empty.")

    if vectorstore is None:
        if not repo_id:
            raise ValueError("Provide either 'vectorstore' or 'repo_id'.")
        logger.info("Loading vectorstore for repo_id=%s", repo_id)
        vectorstore = load_vectorstore(repo_id)

    all_supported_exts = set(EXTENSION_MAP.keys()) | set(GENERIC_EXTENSION_MAP.keys())
    extension_maps = {"primary": EXTENSION_MAP, "generic": GENERIC_EXTENSION_MAP}

    changed_files = get_changed_files(repo_path)
    if not changed_files:
        raise ValueError(
            "Empty diff: no files changed between HEAD~1 and HEAD. "
            "Ensure at least one committed change exists before running the pipeline."
        )

    supported_files = validate_diff_files(changed_files, all_supported_exts)
    if not supported_files:
        raise ValueError(
            f"No supported source files found in the diff for '{repo_path}'. "
            f"{len(changed_files)} file(s) changed but none have a supported extension."
        )

    logger.info(
        "Starting diff pipeline for %d supported file(s) (out of %d total).",
        len(supported_files),
        len(changed_files),
    )

    results: List[Dict[str, str]] = []

    for rel_path in supported_files:
        try:
            hunks = get_function_diff(repo_path, rel_path)
        except Exception as exc:
            logger.exception("Failed to parse diff for %s: %s", rel_path, exc)
            continue

        if not hunks:
            logger.debug("No hunks found for %s; skipping.", rel_path)
            continue

        logger.info("%s: %d hunk(s) detected.", rel_path, len(hunks))

        for hunk in hunks:
            try:
                results.append(
                    process_diff_hunk(
                        hunk=hunk,
                        rel_path=rel_path,
                        repo_path=repo_path,
                        vectorstore=vectorstore,
                        extension_maps=extension_maps,
                    )
                )
            except Exception as exc:
                logger.exception(
                    "Failed processing hunk in %s (function=%s): %s",
                    rel_path,
                    hunk.get("function_name"),
                    exc,
                )

    logger.info("Diff pipeline completed. %d prompt(s) generated.", len(results))
    return results
