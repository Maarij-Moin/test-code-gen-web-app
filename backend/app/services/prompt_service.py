"""Prompt construction utilities for automated test generation."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

try:
    # LangChain Document type for richer type checking when available.
    from langchain.schema import Document
except Exception:  # pragma: no cover - fallback when LangChain is not installed
    Document = Any  # type: ignore


logger = logging.getLogger(__name__)


def build_system_instruction(language: str, framework: str) -> str:
    """Build the system instruction for the LLM.

    Args:
        language: Programming language for the code under test.
        framework: Test framework to target in generated tests.

    Returns:
        Formatted system instruction string.
    """

    instruction = (
        "You are a senior QA engineer specializing in automated testing. "
        "You understand code diffs and update tests to match the new behavior. "
        "Focus on edge cases, regressions, and realistic usage scenarios. "
        "Avoid duplicate tests and keep coverage focused on meaningful behavior. "
        f"Use {framework} conventions and best practices for {language}."
    )

    logger.debug(
        "Built system instruction for language=%s, framework=%s", language, framework
    )
    return instruction


def build_diff_context(old_code: str, new_code: str) -> str:
    """Format the diff context with old and new code blocks.

    Args:
        old_code: Code before the change.
        new_code: Code after the change.

    Returns:
        Formatted diff context.
    """

    old_code = old_code or ""
    new_code = new_code or ""

    diff_context = f"--- OLD CODE ---\n{old_code}\n\n+++ NEW CODE +++\n{new_code}"

    logger.debug("Built diff context with %d old chars and %d new chars", len(old_code), len(new_code))
    return diff_context


def _combine_page_content(chunks: Iterable[Document]) -> str:
    """Combine page_content from LangChain Document objects.

    Args:
        chunks: Iterable of LangChain Document objects.

    Returns:
        Combined string content.
    """

    combined_parts: List[str] = []
    for idx, chunk in enumerate(chunks):
        content = getattr(chunk, "page_content", "")
        if content:
            combined_parts.append(content)
        else:
            logger.debug("Skipping empty chunk at index %d", idx)

    return "\n\n".join(combined_parts)


def build_related_code_context(related_chunks: Optional[List[Document]]) -> str:
    """Format related implementation context.

    Args:
        related_chunks: List of LangChain Document objects.

    Returns:
        Formatted related code context or empty string if none.
    """

    if not related_chunks:
        logger.debug("No related code chunks provided")
        return ""

    combined = _combine_page_content(related_chunks)
    if not combined:
        logger.debug("Related code chunks were empty after combining")
        return ""

    return f"--- RELATED IMPLEMENTATION ---\n{combined}"


def build_existing_tests_context(existing_tests: Optional[List[Document]]) -> str:
    """Format existing tests context.

    Args:
        existing_tests: List of LangChain Document objects.

    Returns:
        Formatted existing tests context or empty string if none.
    """

    if not existing_tests:
        logger.debug("No existing test chunks provided")
        return ""

    combined = _combine_page_content(existing_tests)
    if not combined:
        logger.debug("Existing test chunks were empty after combining")
        return ""

    return f"--- EXISTING TESTS ---\n{combined}"


def generate_test_prompt(
    old_code: str,
    new_code: str,
    related_chunks: Optional[List[Document]],
    existing_tests: Optional[List[Document]],
    metadata: Dict[str, Any],
) -> str:
    """Generate the full test prompt for the LLM.

    Args:
        old_code: Code before the change.
        new_code: Code after the change.
        related_chunks: Related implementation documents.
        existing_tests: Existing test documents.
        metadata: Additional metadata containing language, test framework, file path, and unit name.

    Returns:
        Full prompt string for test generation.
    """

    language = str(metadata.get("language", "")).strip() or "unknown"
    framework = str(metadata.get("test_framework", "")).strip() or "unknown"
    file_path = str(metadata.get("file_path", "")).strip() or "unknown"
    unit_name = str(metadata.get("unit_name", "")).strip() or "unknown"

    system_instruction = build_system_instruction(language, framework)
    diff_context = build_diff_context(old_code, new_code)
    related_context = build_related_code_context(related_chunks)
    existing_tests_context = build_existing_tests_context(existing_tests)

    sections = [
        f"SYSTEM INSTRUCTION:\n{system_instruction}",
        f"FILE: {file_path}",
        f"UNIT: {unit_name}",
        diff_context,
    ]

    if related_context:
        sections.append(related_context)
    if existing_tests_context:
        sections.append(existing_tests_context)

    sections.append(
        "--- TASK ---\n"
        "Generate updated tests that reflect the new code behavior. "
        "Cover edge cases, avoid duplicates, and align with the specified framework."
    )

    final_prompt = "\n\n".join(sections)

    logger.info(
        "Generated test prompt for file=%s unit=%s language=%s framework=%s",
        file_path,
        unit_name,
        language,
        framework,
    )
    return final_prompt
