import os
import logging
from app.services.diff_service import get_changed_files, get_function_diff
from app.services.vectorstore_service import load_vectorstore
from app.services.language_config import EXTENSION_MAP, GENERIC_EXTENSION_MAP

logger = logging.getLogger(__name__)

def retrieve_related_chunks(
    query: str,
    vectorstore,
    k_code: int = 5,
    k_tests: int = 3,
    meta_language_if_known: str | None = None,
) -> tuple[list, list]:
    """Retrieve implementation chunks and existing test chunks related to *query*.

    Args:
        query:                  The changed function name / signature used as the search query.
        vectorstore:            Open Chroma collection for this repo.
        k_code:                 Max implementation chunks to retrieve.
        k_tests:                Max existing test chunks to retrieve.
        meta_language_if_known: When provided, restricts code retrieval to chunks
                                whose ``language`` metadata matches this value
                                (e.g. ``"Python"``, ``"Go"``).  Pass ``None``
                                to search across all languages.

    Returns:
        (code_results, test_results) — lists of LangChain Document objects.
    """
    # Build the code filter — only add language key when we actually know it
    code_filter: dict = {"is_test_file": False}
    if meta_language_if_known:
        code_filter["language"] = meta_language_if_known

    code_results = vectorstore.similarity_search(
        query, k=k_code, filter=code_filter
    )
    test_results = vectorstore.similarity_search(
        query, k=k_tests, filter={"is_test_file": True}
    )
    return code_results, test_results


def generate_test_prompt_from_diff(
    old_code: str,
    new_code: str,
    related_chunks: list,
    meta: dict,
    existing_tests: list | None = None,
) -> str:
    """Build a test-update prompt driven by a git diff hunk.

    Args:
        old_code:       The removed lines from the diff (before the change).
        new_code:       The added lines from the diff (after the change).
        related_chunks: Implementation Document chunks retrieved from the vector DB.
        meta:           Metadata dict from the most relevant implementation chunk
                        (provides language, test_framework, file_path).
        existing_tests: Test file Document chunks retrieved from the vector DB.

    Returns:
        A fully formed prompt string ready to send to an LLM.
    """
    language       = meta.get("language", "Unknown")
    framework      = meta.get("test_framework", "appropriate testing framework")
    file_path      = meta.get("file_path", "<unknown file>")
    function_name  = meta.get("unit_name", "<unknown function>")

    # --- Build context blocks ---
    related_context = "\n\n".join([c.page_content for c in related_chunks]) if related_chunks else ""
    test_context    = "\n\n".join([t.page_content for t in existing_tests])  if existing_tests  else ""

    related_section = (
        f"\n\nRelated implementation context:\n{related_context}"
        if related_context else ""
    )
    existing_tests_section = (
        f"\n\nExisting tests (DO NOT duplicate — use as style guide):\n{test_context}"
        if test_context else ""
    )

    diff_block = (
        f"--- OLD CODE (before change) ---\n{old_code}\n\n"
        f"+++ NEW CODE (after change) ---\n{new_code}"
    )

    prompt = f"""You are an expert QA engineer reviewing a code change in a {language} project.

A function has been modified. Your job is to:
1. Understand WHAT changed between the old and new version.
2. UPDATE or ADD test cases to cover the new behaviour.
3. REMOVE or FIX any tests that are now invalid due to the change.

Rules:
- Use the {framework} testing framework exclusively.
- Cover edge cases, error paths, and standard execution paths.
- Follow {language} naming conventions and best practices.
- Do NOT duplicate any existing tests shown below.

File: {file_path}
Function: {function_name}

{diff_block}{related_section}{existing_tests_section}

Generate the updated test suite now:
"""
    return prompt


def run_diff_pipeline(
    repo_path: str,
    vectorstore=None,
    repo_id: str | None = None,
) -> list[dict]:
    """Full diff-driven test-generation pipeline.

    Flow:
        git diff HEAD~1
          └─ for each changed supported file
              └─ get_function_diff()       → list of changed hunks
                  └─ for each hunk
                      └─ retrieve_related_chunks()      → code + test docs
                          └─ generate_test_prompt_from_diff() → prompt

    Args:
        repo_path:   Path to the git repository root.
        vectorstore: Open Chroma instance. Pass this OR repo_id.
        repo_id:     Repo ID from process_and_store_codebase(). Used when
                     vectorstore is None.

    Returns:
        List of dicts, one per changed hunk::

            {
                "file":          "path/to/file.py",
                "function_name": "my_function",
                "old_code":      "...",
                "new_code":      "...",
                "prompt":        "<LLM prompt>",
            }
    """
    if vectorstore is None:
        if repo_id is None:
            raise ValueError("Provide either 'vectorstore' or 'repo_id'.")
        vectorstore = load_vectorstore(repo_id)

    all_supported_exts = set(EXTENSION_MAP.keys()) | set(GENERIC_EXTENSION_MAP.keys())
    changed_files = get_changed_files(repo_path)
    supported_files = [
        f for f in changed_files
        if os.path.splitext(f)[1].lower() in all_supported_exts
    ]

    if not changed_files:
        raise ValueError(
            f"Empty diff: no files changed between HEAD~1 and HEAD in '{repo_path}'. "
            "Ensure there is at least one committed change before running the diff pipeline."
        )

    if not supported_files:
        raise ValueError(
            f"No supported source files found in the diff for '{repo_path}'. "
            f"{len(changed_files)} file(s) changed but none have a supported extension."
        )

    logger.info(
        "[run_diff_pipeline] %d supported file(s) changed (out of %d total).",
        len(supported_files), len(changed_files),
    )

    results: list[dict] = []

    for rel_path in supported_files:
        abs_path = os.path.join(repo_path, rel_path)
        hunks = get_function_diff(repo_path, rel_path)

        if not hunks:
            logger.debug("[run_diff_pipeline] '%s': no hunks found — skipping.", rel_path)
            continue

        logger.info("[run_diff_pipeline] '%s': %d hunk(s) found.", rel_path, len(hunks))

        for hunk in hunks:
            # Richer query: function name + first 200 chars of new code
            query = f"{hunk['function_name']} {hunk['new_code'][:200]}".strip()

            # Detect language from file extension for filtered retrieval
            ext = os.path.splitext(rel_path)[1].lower()
            lang_info = EXTENSION_MAP.get(ext) or GENERIC_EXTENSION_MAP.get(ext, {})
            language  = lang_info.get("name") or None

            code_chunks, test_chunks = retrieve_related_chunks(
                query, vectorstore, meta_language_if_known=language
            )

            # Derive metadata from the top code result if available
            if code_chunks:
                meta = {**code_chunks[0].metadata, "unit_name": hunk["function_name"]}
            else:
                # Fallback: minimal metadata from the diff itself
                ext = os.path.splitext(rel_path)[1].lower()
                lang_info = EXTENSION_MAP.get(ext) or GENERIC_EXTENSION_MAP.get(ext, {})
                meta = {
                    "language":       lang_info.get("name", "Unknown"),
                    "test_framework": lang_info.get("framework", "N/A"),
                    "file_path":      abs_path,
                    "unit_name":      hunk["function_name"],
                }

            prompt = generate_test_prompt_from_diff(
                old_code       = hunk["old_code"],
                new_code       = hunk["new_code"],
                related_chunks = code_chunks,
                meta           = meta,
                existing_tests = test_chunks,
            )

            results.append({
                "file":          rel_path,
                "function_name": hunk["function_name"],
                "old_code":      hunk["old_code"],
                "new_code":      hunk["new_code"],
                "prompt":        prompt,
            })

    logger.info("[run_diff_pipeline] Generated %d prompt(s).", len(results))
    return results
