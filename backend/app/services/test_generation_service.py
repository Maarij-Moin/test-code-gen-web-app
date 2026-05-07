"""
Test Generation Service — real test file generation via LLM.

This module replaces the old prompt-only approach.  It:

1. Builds language-specific, structured prompts.
2. Calls the LLM via ``llm_service.complete()``.
3. Extracts the code block from the raw LLM response.
4. Syntactically validates the extracted code (Python AST / JS Acorn-lite
   heuristics / Java balanced-brace check).
5. Retries up to ``max_retries`` times on syntax failures, injecting the
   error into the next prompt so the LLM can self-correct.
6. Writes the validated file to disk under ``<repo_root>/auto_tests/``.
7. Returns a structured ``GeneratedTestFile`` with full metadata.

Language support
----------------
==========  =============  ================================
Language    Framework      File naming
==========  =============  ================================
Python      pytest         ``test_<fn>_<file>.py``
JavaScript  Jest           ``<fn>_<file>.test.js``
TypeScript  Jest           ``<fn>_<file>.test.ts``
Java        JUnit 5        ``<ClassName>Test.java``
==========  =============  ================================

Prompt templates
----------------
Each language has a dedicated ``_build_*_system`` and ``_build_user_prompt``
function so prompts remain maintainable and testable in isolation.  The
user prompt is shared across languages; only the system instruction and
the output format specification differ.

Integration with ``test_generator_agent``
-----------------------------------------
``generate_test_file(target, repo_id, …)`` is a drop-in replacement for
the scaffold-only ``generate_for_target`` call in ``test_generator_agent``.
The agent can be updated to call this function directly — or you can call
it standalone from a Celery task.
"""

from __future__ import annotations

import ast
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.llm_service import LLMResponse, complete as llm_complete
from app.services.retrieval_service import retrieve_related_chunks
from app.services.vectorstore_service import load_vectorstore
from app.services.prompt_service import generate_test_prompt

logger = logging.getLogger(__name__)

# Maximum characters of context fed to the LLM prompt (keeps tokens bounded).
_MAX_CONTEXT_CHARS = 3500
_MAX_EXISTING_CHARS = 1500

# Default retry budget for syntax-invalid generations.
_DEFAULT_MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class GeneratedTestFile:
    """A real, validated, disk-persisted test file."""

    # Source information
    target_file: str           # Relative path to the source file being tested.
    function_name: str         # Function / method / class under test.
    language: str              # e.g. "Python"
    framework: str             # e.g. "pytest"
    intent: str                # "regression" | "new_behaviour" | "deletion"

    # Output
    test_file_path: str        # Absolute path where the file was written.
    content: str               # Final validated content on disk.

    # Provenance
    prompt_system: str         # System prompt sent to the LLM.
    prompt_user: str           # User prompt sent to the LLM.
    llm_model: str             # Model that generated the content.
    llm_provider: str          # Provider name.
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    retry_count: int = 0       # How many retries were needed.
    syntax_valid: bool = True
    generated_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )


@dataclass
class GenerationRequest:
    """All inputs needed to generate one test file."""

    # Source diff context
    old_code: str
    new_code: str

    # Target metadata
    target_file: str          # Relative path.
    abs_file_path: str        # Absolute path for import helpers.
    function_name: str
    language: str
    framework: str
    intent: str
    priority: int

    # Retrieval context (populated before calling the service)
    code_chunks: list[Any] = field(default_factory=list)
    test_chunks: list[Any] = field(default_factory=list)

    # Repair context
    failure_logs: str | None = None
    repair_attempt: int = 0


# ---------------------------------------------------------------------------
# Language-specific prompt templates
# ---------------------------------------------------------------------------

def _compress(chunks: list[Any], max_chars: int) -> str:
    """Join chunk page_content up to *max_chars* characters.

    Args:
        chunks:    List of LangChain Document objects.
        max_chars: Hard character limit for the combined string.

    Returns:
        Truncated combined string.
    """
    combined = "\n\n".join(
        getattr(c, "page_content", str(c)) for c in chunks if c
    )
    if len(combined) <= max_chars:
        return combined
    return combined[: max_chars - 3] + "..."


def _build_python_system(framework: str = "pytest") -> str:
    return (
        f"You are a senior Python QA engineer. "
        f"Generate a complete, runnable {framework} test file. "
        "Rules:\n"
        "- Use only the standard library plus pytest.\n"
        "- Every test function must start with `test_`.\n"
        "- Include at minimum: happy path, edge case, error path.\n"
        "- Do NOT include markdown fences, explanations, or any text outside the Python code.\n"
        "- Output ONLY the raw Python source code."
    )


def _build_js_system(framework: str = "jest", lang: str = "JavaScript") -> str:
    return (
        f"You are a senior {lang} QA engineer. "
        f"Generate a complete, runnable {framework} test file. "
        "Rules:\n"
        "- Use CommonJS `require` or ES module `import` as appropriate.\n"
        "- Include describe/it blocks with expect assertions.\n"
        "- Cover happy path, edge cases, and error handling.\n"
        "- Do NOT include markdown fences, explanations, or any text outside the JS/TS code.\n"
        "- Output ONLY the raw source code."
    )


def _build_java_system() -> str:
    return (
        "You are a senior Java QA engineer. "
        "Generate a complete, runnable JUnit 5 test class. "
        "Rules:\n"
        "- Import `org.junit.jupiter.api.*` and `static org.junit.jupiter.api.Assertions.*`.\n"
        "- Annotate test methods with `@Test`.\n"
        "- The class name must end with `Test`.\n"
        "- Cover happy path, edge cases, and expected exceptions.\n"
        "- Do NOT include markdown fences, explanations, or any text outside the Java code.\n"
        "- Output ONLY the raw Java source code."
    )


def _select_system_prompt(language: str, framework: str) -> str:
    """Select the system prompt for the given language/framework combination.

    Args:
        language:  Language string (e.g. "Python", "JavaScript", "Java").
        framework: Framework string (e.g. "pytest", "jest", "junit").

    Returns:
        System prompt string.
    """
    lang = language.lower()
    if lang in {"python", "py"}:
        return _build_python_system(framework)
    if lang in {"javascript", "js"}:
        return _build_js_system(framework, "JavaScript")
    if lang in {"typescript", "ts"}:
        return _build_js_system(framework, "TypeScript")
    if lang == "java":
        return _build_java_system()
    # Generic fallback
    return (
        f"You are a senior QA engineer. Generate a complete, runnable {framework} test file "
        f"for {language}. Output ONLY the raw source code, no markdown."
    )


def _build_user_prompt(req: GenerationRequest) -> str:
    """Build the shared user prompt from the diff and context.

    The prompt structure is:
    1. Diff block (old → new code).
    2. Related implementation context (from ChromaDB).
    3. Existing test style examples (from ChromaDB).
    4. Failure logs if in repair mode.
    5. Task instruction.

    Args:
        req: Populated ``GenerationRequest``.

    Returns:
        User prompt string.
    """
    sections: list[str] = []

    sections.append(f"FILE: {req.abs_file_path}")
    sections.append(f"FUNCTION/UNIT: {req.function_name}")
    sections.append(f"INTENT: {req.intent}")

    sections.append(
        f"--- DIFF (old → new) ---\n"
        f"OLD:\n{req.old_code or '(new function)'}\n\n"
        f"NEW:\n{req.new_code or '(function deleted)'}"
    )

    if req.code_chunks:
        ctx = _compress(req.code_chunks, _MAX_CONTEXT_CHARS)
        sections.append(f"--- RELATED IMPLEMENTATION ---\n{ctx}")

    if req.test_chunks:
        existing = _compress(req.test_chunks, _MAX_EXISTING_CHARS)
        sections.append(
            f"--- EXISTING TESTS (match style, do NOT duplicate) ---\n{existing}"
        )

    if req.failure_logs:
        sections.append(
            f"--- PREVIOUS ATTEMPT FAILED (repair attempt {req.repair_attempt}) ---\n"
            f"{req.failure_logs[:1500]}\n"
            "Fix ONLY the issues shown above. Keep the rest of the test file intact."
        )

    sections.append(
        "--- TASK ---\n"
        "Generate the complete test file now. "
        "Output ONLY the raw source code — no markdown, no explanations, no extra text."
    )

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Response extraction
# ---------------------------------------------------------------------------

def _extract_code(raw: str, language: str) -> str:
    """Strip markdown fences and explanatory prose from LLM output.

    The LLM sometimes wraps the code in a fenced block even when instructed
    not to.  This function extracts the inner content and strips leading /
    trailing whitespace.

    Args:
        raw:      Raw string returned by the LLM.
        language: Language hint for fence detection.

    Returns:
        Cleaned source code string.
    """
    # Try to extract a fenced block first
    lang_aliases = {
        "python": ["python", "py"],
        "javascript": ["javascript", "js"],
        "typescript": ["typescript", "ts"],
        "java": ["java"],
    }.get(language.lower(), [language.lower()])

    # Matches ```lang or ``` followed by code then ```
    for alias in lang_aliases + [""]:
        pattern = rf"```{re.escape(alias)}\s*\n?([\s\S]+?)```"
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # No fence found — return the raw output stripped of leading blank lines
    return raw.strip()


# ---------------------------------------------------------------------------
# Syntax validation
# ---------------------------------------------------------------------------

def _validate_python(code: str) -> tuple[bool, str]:
    """Parse *code* with ``ast.parse``; return (valid, error_message).

    Args:
        code: Python source code string.

    Returns:
        (True, "") on success, (False, error_msg) on syntax error.
    """
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as exc:
        return False, f"SyntaxError at line {exc.lineno}: {exc.msg}"


def _validate_js(code: str) -> tuple[bool, str]:
    """Heuristic JS/TS syntax check (no external parser required).

    Checks balanced braces/brackets/parens and that at least one
    ``it(`` or ``test(`` call exists.

    Args:
        code: JavaScript/TypeScript source code string.

    Returns:
        (True, "") if heuristically valid, (False, error_msg) otherwise.
    """
    # Balanced brace check
    depth = 0
    for ch in code:
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        if depth < 0:
            return False, "Unbalanced braces/brackets/parens detected."
    if depth != 0:
        return False, f"Unbalanced braces/brackets/parens (depth={depth} at EOF)."
    # Must contain at least one test assertion
    if not re.search(r"\bit\s*\(|\btest\s*\(|describe\s*\(", code):
        return False, "No it/test/describe block found."
    return True, ""


def _validate_java(code: str) -> tuple[bool, str]:
    """Heuristic Java syntax check.

    Verifies balanced braces and the presence of ``@Test`` annotation.

    Args:
        code: Java source code string.

    Returns:
        (True, "") if heuristically valid, (False, error_msg) otherwise.
    """
    depth = 0
    for ch in code:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if depth < 0:
            return False, "Unbalanced braces detected."
    if depth != 0:
        return False, f"Unbalanced braces (depth={depth} at EOF)."
    if "@Test" not in code:
        return False, "No @Test annotation found."
    return True, ""


def validate_syntax(code: str, language: str) -> tuple[bool, str]:
    """Dispatch to the correct syntax validator for *language*.

    Args:
        code:     Source code to validate.
        language: Language string (case-insensitive).

    Returns:
        (valid: bool, error_message: str).
    """
    lang = language.lower()
    if lang in {"python", "py"}:
        return _validate_python(code)
    if lang in {"javascript", "js", "typescript", "ts"}:
        return _validate_js(code)
    if lang == "java":
        return _validate_java(code)
    # Unknown language — accept anything
    return True, ""


# ---------------------------------------------------------------------------
# File naming
# ---------------------------------------------------------------------------

def _safe(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", name or "test")
    return cleaned.strip("_") or "test"


def _resolve_output_path(
    repo_path: str,
    target_file: str,
    function_name: str,
    language: str,
) -> Path:
    """Compute the output file path inside ``<repo_root>/auto_tests/``.

    Args:
        repo_path:     Absolute path to the repository root.
        target_file:   Relative path to the source file being tested.
        function_name: Function/class being tested.
        language:      Programming language.

    Returns:
        Absolute ``Path`` for the test file (parent dirs are created).
    """
    test_dir = Path(repo_path) / "auto_tests"
    test_dir.mkdir(parents=True, exist_ok=True)

    safe_fn = _safe(function_name)
    safe_file = _safe(target_file.replace(os.sep, "_").replace("/", "_"))
    stem = f"{safe_fn}_{safe_file}"

    lang = language.lower()
    if lang in {"javascript", "js"}:
        filename = f"{stem}.test.js"
    elif lang in {"typescript", "ts"}:
        filename = f"{stem}.test.ts"
    elif lang == "java":
        # Java convention: ClassName → ClassNameTest.java
        class_name = "".join(w.capitalize() for w in safe_fn.split("_"))
        filename = f"{class_name}Test.java"
    else:
        filename = f"test_{stem}.py"

    return test_dir / filename


# ---------------------------------------------------------------------------
# Core generation function
# ---------------------------------------------------------------------------

def generate_test_file(
    req: GenerationRequest,
    repo_path: str,
    *,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> GeneratedTestFile:
    """Generate a real, validated test file for a single ``GenerationRequest``.

    Flow
    ----
    1. Build system + user prompts.
    2. Call ``llm_service.complete()``.
    3. Extract code block from the raw response.
    4. Validate syntax.
    5. If invalid and retries remain: inject the error into the repair
       prompt and retry.
    6. Write the (best-available) code to disk.
    7. Return a fully populated ``GeneratedTestFile``.

    Args:
        req:         A populated ``GenerationRequest``.
        repo_path:   Absolute path to the repository root.
        max_retries: Maximum LLM call + repair attempts.

    Returns:
        ``GeneratedTestFile`` with ``syntax_valid`` and ``retry_count`` set.
    """
    system_prompt = _select_system_prompt(req.language, req.framework)
    user_prompt = _build_user_prompt(req)

    last_content = ""
    last_resp: LLMResponse | None = None
    retry_count = 0
    current_failure: str | None = None

    for attempt in range(1, max_retries + 1):
        # Inject syntax failure from previous attempt into the user prompt
        if current_failure and attempt > 1:
            repair_req = GenerationRequest(
                **{  # type: ignore[arg-type]
                    **req.__dict__,
                    "failure_logs": (
                        f"SYNTAX ERROR from attempt {attempt - 1}:\n{current_failure}\n\n"
                        + (req.failure_logs or "")
                    ),
                    "repair_attempt": attempt - 1,
                }
            )
            user_prompt = _build_user_prompt(repair_req)

        logger.info(
            "[test_generation_service] LLM call attempt %d/%d. target=%s::%s lang=%s",
            attempt, max_retries, req.target_file, req.function_name, req.language,
        )

        try:
            resp = llm_complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except RuntimeError as exc:
            logger.error(
                "[test_generation_service] LLM call failed on attempt %d: %s",
                attempt, exc,
            )
            current_failure = str(exc)
            retry_count += 1
            continue

        last_resp = resp
        code = _extract_code(resp.content, req.language)
        valid, error_msg = validate_syntax(code, req.language)

        if valid:
            last_content = code
            retry_count = attempt - 1
            logger.info(
                "[test_generation_service] Valid %s code generated on attempt %d.",
                req.language, attempt,
            )
            break

        logger.warning(
            "[test_generation_service] Syntax invalid on attempt %d: %s",
            attempt, error_msg,
        )
        current_failure = error_msg
        last_content = code  # Keep last attempt even if invalid
        retry_count = attempt

    # ------------------------------------------------------------------
    # Write to disk (even if syntax is still invalid — caller may inspect)
    # ------------------------------------------------------------------
    out_path = _resolve_output_path(
        repo_path, req.target_file, req.function_name, req.language
    )

    # Write atomically: temp file then rename (safe on same filesystem)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp_path.write_text(last_content, encoding="utf-8")
    tmp_path.replace(out_path)

    syntax_valid = current_failure is None or retry_count < max_retries

    logger.info(
        "[test_generation_service] Written %s (%d bytes). syntax_valid=%s retries=%d",
        out_path, len(last_content), syntax_valid, retry_count,
    )

    return GeneratedTestFile(
        target_file=req.target_file,
        function_name=req.function_name,
        language=req.language,
        framework=req.framework,
        intent=req.intent,
        test_file_path=str(out_path),
        content=last_content,
        prompt_system=system_prompt,
        prompt_user=user_prompt,
        llm_model=last_resp.model if last_resp else "unknown",
        llm_provider=last_resp.provider if last_resp else "unknown",
        prompt_tokens=last_resp.prompt_tokens if last_resp else 0,
        completion_tokens=last_resp.completion_tokens if last_resp else 0,
        latency_ms=last_resp.latency_ms if last_resp else 0,
        retry_count=retry_count,
        syntax_valid=syntax_valid,
    )


# ---------------------------------------------------------------------------
# Batch helper (used by test_generator_agent)
# ---------------------------------------------------------------------------

@dataclass
class BatchGenerationResult:
    """Aggregated result for a batch of test files."""
    succeeded: list[GeneratedTestFile] = field(default_factory=list)
    failed: list[dict[str, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.succeeded) + len(self.failed)

    @property
    def success_rate(self) -> float:
        return len(self.succeeded) / self.total if self.total else 0.0


def generate_batch(
    requests: list[GenerationRequest],
    repo_path: str,
    *,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> BatchGenerationResult:
    """Generate test files for a list of requests, collecting errors without aborting.

    Args:
        requests:    List of ``GenerationRequest`` instances.
        repo_path:   Absolute repository root path.
        max_retries: LLM retry budget per request.

    Returns:
        ``BatchGenerationResult`` with succeeded and failed lists.
    """
    result = BatchGenerationResult()
    logger.info(
        "[test_generation_service] Batch generation: %d request(s).", len(requests)
    )

    for req in requests:
        try:
            gtf = generate_test_file(req, repo_path, max_retries=max_retries)
            result.succeeded.append(gtf)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "[test_generation_service] Batch item failed: %s::%s — %s",
                req.target_file, req.function_name, exc,
            )
            result.failed.append({
                "target_file": req.target_file,
                "function_name": req.function_name,
                "error": str(exc),
            })

    logger.info(
        "[test_generation_service] Batch complete. succeeded=%d failed=%d",
        len(result.succeeded), len(result.failed),
    )
    return result


# ---------------------------------------------------------------------------
# Retrieval helper (builds a GenerationRequest from a TestTarget)
# ---------------------------------------------------------------------------

def build_request_from_target(
    target: Any,           # app.agents.planner_agent.TestTarget
    repo_id: str,
    failure_logs: str | None = None,
    repair_attempt: int = 0,
) -> GenerationRequest:
    """Construct a ``GenerationRequest`` from a planner ``TestTarget``.

    Fetches related code and test chunks from the vectorstore automatically.

    Args:
        target:         ``TestTarget`` from the planner agent.
        repo_id:        Chroma collection identifier.
        failure_logs:   Optional logs from a previous failed validation.
        repair_attempt: Which repair cycle this is.

    Returns:
        Fully populated ``GenerationRequest`` ready for ``generate_test_file``.
    """
    code_chunks: list[Any] = []
    test_chunks: list[Any] = []

    try:
        vs = load_vectorstore(repo_id)
        code_chunks, test_chunks = retrieve_related_chunks(
            query=target.query,
            vectorstore=vs,
            k_code=5,
            k_tests=3,
            meta_language_if_known=target.language,
        )
        logger.debug(
            "[test_generation_service] Retrieved %d code + %d test chunks for %s::%s",
            len(code_chunks), len(test_chunks), target.file, target.function_name,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[test_generation_service] Retrieval failed for %s — empty context: %s",
            target.file, exc,
        )

    return GenerationRequest(
        old_code=target.old_code,
        new_code=target.new_code,
        target_file=target.file,
        abs_file_path=target.abs_file_path,
        function_name=target.function_name,
        language=target.language,
        framework=target.framework,
        intent=target.intent,
        priority=target.priority,
        code_chunks=code_chunks,
        test_chunks=test_chunks,
        failure_logs=failure_logs,
        repair_attempt=repair_attempt,
    )
