"""Production-grade AI test generation engine.

This module builds optimized prompts for different test types and languages,
performs context compression, and returns structured outputs for downstream
LLM execution and file creation.
"""

from __future__ import annotations

import hashlib
import logging
import textwrap
from dataclasses import dataclass
from typing import Any, Iterable


logger = logging.getLogger(__name__)


@dataclass
class GenerationInput:
    diff: str
    retrieved_chunks: list[str]
    existing_tests: list[str]
    metadata: dict[str, Any]


@dataclass
class GeneratedTest:
    file_path: str
    content: str
    confidence: float


_TEST_TYPES = ("unit", "integration", "edge", "regression")


def _compress_context(chunks: Iterable[str], max_chars: int = 4000) -> str:
    """Compress context to keep prompts within a reasonable size."""

    combined = "\n\n".join([c for c in chunks if c])
    if len(combined) <= max_chars:
        return combined
    return combined[: max_chars - 3] + "..."


def _style_hint(existing_tests: Iterable[str]) -> str:
    """Infer test style hints from existing tests to match conventions."""

    joined = "\n".join(existing_tests)
    if "pytest" in joined or "def test_" in joined:
        return "Use pytest style with fixtures and assert statements."
    if "describe(" in joined or "it(" in joined:
        return "Use Jest style with describe/it and expect assertions."
    if "@Test" in joined or "org.junit" in joined:
        return "Use JUnit annotations and assertions."
    return "Follow the repository's dominant test conventions."


def _prevent_duplicates(existing_tests: Iterable[str], new_tests: str) -> str:
    """Remove exact duplicate test blocks if they already exist."""

    existing_hashes = {hashlib.md5(t.encode("utf-8")).hexdigest() for t in existing_tests}
    if hashlib.md5(new_tests.encode("utf-8")).hexdigest() in existing_hashes:
        return ""
    return new_tests


def _language_defaults(language: str) -> dict[str, str]:
    lang = (language or "").lower()
    if lang in {"python", "py"}:
        return {"framework": "pytest", "ext": "py", "prefix": "test_"}
    if lang in {"javascript", "js"}:
        return {"framework": "jest", "ext": "test.js", "prefix": ""}
    if lang in {"typescript", "ts"}:
        return {"framework": "jest", "ext": "test.ts", "prefix": ""}
    if lang in {"java"}:
        return {"framework": "junit", "ext": "Test.java", "prefix": ""}
    return {"framework": "pytest", "ext": "py", "prefix": "test_"}


def _build_prompt(test_type: str, data: GenerationInput) -> str:
    meta = data.metadata or {}
    language = meta.get("language", "unknown")
    framework = meta.get("test_framework") or _language_defaults(language)["framework"]
    style = _style_hint(data.existing_tests)

    context = _compress_context(data.retrieved_chunks)
    existing = _compress_context(data.existing_tests, max_chars=2000)

    prompt = f"""
You are a senior QA engineer specializing in {language} testing.
Generate {test_type} tests using {framework}.
{style}

Diff:
{data.diff}

Related context:
{context}

Existing tests (do not duplicate):
{existing}

Output only the test file content.
"""
    return textwrap.dedent(prompt).strip()


def _estimate_confidence(diff: str, context: str) -> float:
    """Heuristic confidence score based on available context size."""

    score = 0.5
    if diff:
        score += 0.2
    if context:
        score += 0.2
    return min(score, 0.95)


def generate_tests(data: GenerationInput) -> dict[str, GeneratedTest]:
    """Generate prompts and suggested file paths for multiple test types.

    Returns a dict keyed by test type.
    """

    meta = data.metadata or {}
    language = meta.get("language", "python")
    unit_name = meta.get("unit_name", "module")
    defaults = _language_defaults(language)

    results: dict[str, GeneratedTest] = {}
    for test_type in _TEST_TYPES:
        prompt = _build_prompt(test_type, data)
        suggested_name = f"{defaults['prefix']}{unit_name}_{test_type}.{defaults['ext']}"
        content = _prevent_duplicates(data.existing_tests, prompt)
        confidence = _estimate_confidence(data.diff, "".join(data.retrieved_chunks))

        results[test_type] = GeneratedTest(
            file_path=suggested_name,
            content=content,
            confidence=confidence,
        )

        logger.info("[test_generation] %s tests prepared: %s", test_type, suggested_name)

    return results
