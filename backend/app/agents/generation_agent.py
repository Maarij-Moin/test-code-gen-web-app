"""Generation agent for producing test file drafts."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from app.services.prompt_service import generate_test_prompt


logger = logging.getLogger(__name__)


@dataclass
class GeneratedTestArtifact:
    file_path: str
    content: str
    prompt: str


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", name or "test")
    return cleaned.strip("_") or "test"


def _python_test_template(file_path: str, function_name: str | None) -> str:
    target = function_name or "unknown"
    return (
        "import importlib.util\n"
        "import pathlib\n\n"
        f"FILE_PATH = pathlib.Path(r\"{file_path}\")\n\n"
        "def _load_module():\n"
        "    spec = importlib.util.spec_from_file_location('target_module', FILE_PATH)\n"
        "    module = importlib.util.module_from_spec(spec)\n"
        "    assert spec and spec.loader\n"
        "    spec.loader.exec_module(module)\n"
        "    return module\n\n"
        f"def test_{_safe_filename(target)}_exists():\n"
        "    module = _load_module()\n"
        f"    assert hasattr(module, '{target}')\n"
    )


def generate_tests(
    repo_path: str,
    diff_results: list[dict[str, Any]],
    retrieval_map: dict[str, dict[str, list[Any]]],
    failure_logs: str | None = None,
) -> list[GeneratedTestArtifact]:
    """Generate test artifacts for each diff hunk.

    Args:
        repo_path: Local repository path.
        diff_results: Diff pipeline results.
        retrieval_map: Retrieved context keyed by file/function.
        failure_logs: Optional validation logs for repair loop.

    Returns:
        List of GeneratedTestArtifact instances.
    """

    logger.info("[generation_agent] Generating tests for %d hunks", len(diff_results))
    artifacts: list[GeneratedTestArtifact] = []

    for hunk in diff_results:
        rel_path = hunk.get("file") or ""
        function_name = hunk.get("function_name") or ""
        abs_path = os.path.join(repo_path, rel_path)
        key = f"{rel_path}:{function_name}"
        context = retrieval_map.get(key, {})

        prompt = generate_test_prompt(
            old_code=hunk.get("old_code"),
            new_code=hunk.get("new_code"),
            related_chunks=context.get("code_chunks") or [],
            existing_tests=context.get("test_chunks") or [],
            metadata={
                "file_path": abs_path,
                "unit_name": function_name,
                "language": context.get("language", "Unknown"),
                "test_framework": context.get("test_framework", "pytest"),
                "failure_logs": failure_logs or "",
            },
        )

        test_dir = Path(repo_path) / "auto_tests"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / f"test_{_safe_filename(function_name)}.py"
        content = _python_test_template(abs_path, function_name)

        # Persist generated test file to disk for validation runs.
        test_file.write_text(content, encoding="utf-8")

        artifacts.append(
            GeneratedTestArtifact(file_path=str(test_file), content=content, prompt=prompt)
        )

    return artifacts
