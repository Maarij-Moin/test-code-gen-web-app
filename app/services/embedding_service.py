import ast
import logging
import os
import re
import hashlib
import threading
from typing import Generator
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from app.services.diff_service import get_changed_files, get_function_diff

logger = logging.getLogger(__name__)

# Base directory where all per-repo Chroma DBs are stored
CHROMA_BASE_DIR = "./chroma_polyglot_storage"


def make_repo_id(repo_path: str) -> str:
    """Return a stable, filesystem-safe ID derived from the canonical repo path.

    Using a SHA-256 hash of the absolute path guarantees:
    - The same path always produces the same ID (deterministic)
    - Different paths never collide
    - The ID is safe to use as a directory name and Chroma collection name
    """
    canonical = os.path.realpath(repo_path)
    return "repo_" + hashlib.sha256(canonical.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Embedding model — singleton (loaded once, reused across all calls)
# ---------------------------------------------------------------------------
_embeddings_instance: HuggingFaceEmbeddings | None = None
_embeddings_lock = threading.Lock()


def _get_embeddings() -> HuggingFaceEmbeddings:
    """Return the shared embedding model, loading it on first call only.

    Thread-safe singleton: the model is expensive to load (~1-2 s and several
    hundred MB of RAM).  Reusing a single instance avoids that cost on every
    call to process_and_store_codebase() or load_vectorstore().
    """
    global _embeddings_instance
    if _embeddings_instance is None:
        with _embeddings_lock:
            if _embeddings_instance is None:  # double-checked locking
                logger.info("Loading embedding model (first call)...")
                _embeddings_instance = HuggingFaceEmbeddings(
                    model_name="BAAI/bge-base-en-v1.5",
                    model_kwargs={"device": "cpu"},
                    encode_kwargs={"normalize_embeddings": True},
                )
                logger.info("Embedding model loaded.")
    return _embeddings_instance


def load_vectorstore(repo_id: str) -> Chroma:
    """Re-open an existing per-repo Chroma collection by its repo_id.

    Use this to query a repo that was already processed and persisted.
    Raises FileNotFoundError if the repo_id has never been processed.
    """
    persist_dir = os.path.join(CHROMA_BASE_DIR, repo_id)
    if not os.path.isdir(persist_dir):
        raise FileNotFoundError(
            f"No persisted DB found for repo_id '{repo_id}'. "
            "Run process_and_store_codebase() first."
        )
    return Chroma(
        collection_name=repo_id,
        embedding_function=_get_embeddings(),
        persist_directory=persist_dir,
    )

# ---------------------------------------------------------------------------
# Function / class -level extraction helpers
# ---------------------------------------------------------------------------

# Maximum characters before we sub-chunk a unit with a generic splitter
MAX_UNIT_CHARS = 4_000

# --- Regex patterns: match the START of each top-level declaration --------
# We find every match position, then slice the file between consecutive
# positions.  This gives one unit per function/class without needing a
# full parser or brace-counter.
_FUNC_SPLIT_PATTERNS: dict[str, re.Pattern] = {
    ".go":   re.compile(r'^func\s+', re.MULTILINE),
    ".rs":   re.compile(r'^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+', re.MULTILINE),
    ".php":  re.compile(r'^\s*(?:(?:public|protected|private|static|abstract|final)\s+)*function\s+', re.MULTILINE),
    ".rb":   re.compile(r'^\s*(?:def |class )', re.MULTILINE),
    ".swift": re.compile(r'^\s*(?:(?:public|private|internal|open|fileprivate|static|class|override|final)\s+)*func\s+', re.MULTILINE),
    ".java":  re.compile(
        r'^\s*(?:(?:public|private|protected|static|final|abstract|synchronized|native|default)\s+)'
        r'+[\w<>\[\],\s]+\s+\w+\s*\(',
        re.MULTILINE,
    ),
    ".kt":   re.compile(
        r'^\s*(?:(?:public|private|protected|internal|open|override|suspend|inline|operator|infix)\s+)*fun\s+',
        re.MULTILINE,
    ),
    ".cs":   re.compile(
        r'^\s*(?:(?:public|private|protected|internal|static|virtual|override|abstract|async|sealed|readonly)\s+)'
        r'+[\w<>\[\],\s?]+\s+\w+\s*\(',
        re.MULTILINE,
    ),
    ".scala": re.compile(r'^\s*(?:(?:def|class|object|trait)\s+)', re.MULTILINE),
}
# JS / TS share the same pattern
_JS_DECL = re.compile(
    r'^(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\s+\w+|class\s+\w+)'
    r'|^(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:\([^)]*\)|\w+)\s*=>',
    re.MULTILINE,
)
for _e in (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"):
    _FUNC_SPLIT_PATTERNS[_e] = _JS_DECL
# C / C++ — free function or class/struct/namespace keyword
_C_DECL = re.compile(
    r'^(?:[\w:*&<>]+\s+)+\w+\s*\([^;]*$|^\s*(?:class|struct|namespace)\s+',
    re.MULTILINE,
)
for _e in (".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx"):
    _FUNC_SPLIT_PATTERNS[_e] = _C_DECL


def _extract_python_units(content: str) -> Generator[tuple[str, str, str, int, int], None, None]:
    """Yield (code, name, unit_type, start_line, end_line) for every
    top-level function and class using Python's built-in AST parser.
    Nested functions/methods are kept inside their parent class/function.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        yield content, "<module>", "module", 1, content.count("\n") + 1
        return

    lines = content.splitlines(keepends=True)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            code = "".join(lines[node.lineno - 1 : node.end_lineno])
            yield code, node.name, "function", node.lineno, node.end_lineno
        elif isinstance(node, ast.ClassDef):
            code = "".join(lines[node.lineno - 1 : node.end_lineno])
            yield code, node.name, "class", node.lineno, node.end_lineno


def _split_by_declarations(content: str, pattern: re.Pattern) -> list[tuple[str, int, int]]:
    """Slice *content* between every declaration boundary found by *pattern*.
    Returns list of (unit_text, start_line, end_line).
    """
    matches = list(pattern.finditer(content))
    if not matches:
        return [(content, 1, content.count("\n") + 1)]

    positions = [m.start() for m in matches] + [len(content)]
    units: list[tuple[str, int, int]] = []

    # Preamble before the first declaration (imports, constants, etc.)
    if positions[0] > 0:
        preamble = content[: positions[0]].strip()
        if preamble:
            units.append((preamble, 1, preamble.count("\n") + 1))

    for i, match in enumerate(matches):
        unit_text = content[positions[i] : positions[i + 1]].strip()
        if not unit_text:
            continue
        start_line = content[: positions[i]].count("\n") + 1
        end_line   = start_line + unit_text.count("\n")
        units.append((unit_text, start_line, end_line))

    return units


def _sub_chunk(text: str, lang_info: dict, use_generic: bool) -> list[str]:
    """Break an oversized unit into smaller pieces using the appropriate splitter."""
    if use_generic or "lang" not in lang_info:
        splitter = RecursiveCharacterTextSplitter(chunk_size=MAX_UNIT_CHARS, chunk_overlap=100)
    else:
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=lang_info["lang"], chunk_size=MAX_UNIT_CHARS, chunk_overlap=100
        )
    return splitter.split_text(text)


def _chunk_by_units(
    content: str,
    ext: str,
    lang_info: dict,
    use_generic: bool,
) -> Generator[tuple[str, dict], None, None]:
    """Yield (chunk_text, extra_metadata) pairs at function / class granularity.

    Strategy priority:
      1. Python  → AST (exact node boundaries via ast module)
      2. Languages in _FUNC_SPLIT_PATTERNS → regex declaration-boundary split
      3. Everything else → LangChain language-aware splitter (large chunk_size
         so it rarely cuts inside a single function)
    """

    def _emit(text: str, name: str, unit_type: str, strategy: str,
              start: int, end: int, use_generic: bool = False) -> Generator:
        """Yield the unit directly, or sub-chunk it if it's too large."""
        if len(text) <= MAX_UNIT_CHARS:
            yield text, {"unit_name": name, "unit_type": unit_type,
                         "strategy": strategy, "start_line": start, "end_line": end}
        else:
            for sub in _sub_chunk(text, lang_info, use_generic):
                yield sub, {"unit_name": name, "unit_type": unit_type,
                            "strategy": strategy + "(sub-chunked)",
                            "start_line": start, "end_line": end}

    # --- Strategy 1: Python AST ---
    if ext == ".py":
        had_units = False
        for code, name, unit_type, s, e in _extract_python_units(content):
            had_units = True
            yield from _emit(code, name, unit_type, "ast", s, e)
        if not had_units:
            # File has no top-level defs (e.g. only imports) – store whole file
            yield content, {"unit_name": "<module>", "unit_type": "module",
                            "strategy": "ast", "start_line": 1,
                            "end_line": content.count("\n") + 1}
        return

    # --- Strategy 2: Regex declaration-boundary split ---
    if ext in _FUNC_SPLIT_PATTERNS:
        units = _split_by_declarations(content, _FUNC_SPLIT_PATTERNS[ext])
        for unit_text, s, e in units:
            yield from _emit(unit_text, "<unit>", "function/class",
                             "regex-split", s, e, use_generic)
        return

    # --- Strategy 3: LangChain splitter (large window, respects lang separators) ---
    if use_generic or "lang" not in lang_info:
        splitter = RecursiveCharacterTextSplitter(chunk_size=3_000, chunk_overlap=0)
        strategy = "generic-splitter"
    else:
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=lang_info["lang"], chunk_size=3_000, chunk_overlap=0
        )
        strategy = "lang-splitter"

    for i, chunk in enumerate(splitter.split_text(content)):
        yield chunk, {"unit_name": f"<chunk-{i}>", "unit_type": "chunk",
                      "strategy": strategy, "start_line": -1, "end_line": -1}


# ---------------------------------------------------------------------------
# Languages with native LangChain language-aware splitter support
# ---------------------------------------------------------------------------
EXTENSION_MAP = {
    # Python
    ".py":      {"lang": Language.PYTHON,   "name": "Python",          "framework": "pytest"},
    ".pyw":     {"lang": Language.PYTHON,   "name": "Python",          "framework": "pytest"},

    # JavaScript / TypeScript
    ".js":      {"lang": Language.JS,       "name": "JavaScript",      "framework": "Jest"},
    ".mjs":     {"lang": Language.JS,       "name": "JavaScript",      "framework": "Jest"},
    ".cjs":     {"lang": Language.JS,       "name": "JavaScript",      "framework": "Jest"},
    ".jsx":     {"lang": Language.JS,       "name": "JavaScript",      "framework": "Jest"},
    ".ts":      {"lang": Language.TS,       "name": "TypeScript",      "framework": "Jest"},
    ".tsx":     {"lang": Language.TS,       "name": "TypeScript",      "framework": "Jest"},

    # Java / Kotlin / Scala
    ".java":    {"lang": Language.JAVA,     "name": "Java",            "framework": "JUnit"},
    ".kt":      {"lang": Language.KOTLIN,   "name": "Kotlin",          "framework": "JUnit / kotlin.test"},
    ".kts":     {"lang": Language.KOTLIN,   "name": "Kotlin",          "framework": "JUnit / kotlin.test"},
    ".scala":   {"lang": Language.SCALA,    "name": "Scala",           "framework": "ScalaTest"},

    # Go
    ".go":      {"lang": Language.GO,       "name": "Go",              "framework": "testing"},

    # C / C++
    ".c":       {"lang": Language.C,        "name": "C",               "framework": "Unity / CMock"},
    ".h":       {"lang": Language.C,        "name": "C",               "framework": "Unity / CMock"},
    ".cpp":     {"lang": Language.CPP,      "name": "C++",             "framework": "Google Test"},
    ".cc":      {"lang": Language.CPP,      "name": "C++",             "framework": "Google Test"},
    ".cxx":     {"lang": Language.CPP,      "name": "C++",             "framework": "Google Test"},
    ".hpp":     {"lang": Language.CPP,      "name": "C++",             "framework": "Google Test"},
    ".hxx":     {"lang": Language.CPP,      "name": "C++",             "framework": "Google Test"},

    # Rust
    ".rs":      {"lang": Language.RUST,     "name": "Rust",            "framework": "cargo test"},

    # Swift
    ".swift":   {"lang": Language.SWIFT,    "name": "Swift",           "framework": "XCTest"},

    # Ruby
    ".rb":      {"lang": Language.RUBY,     "name": "Ruby",            "framework": "RSpec"},
    ".gemspec": {"lang": Language.RUBY,     "name": "Ruby",            "framework": "RSpec"},

    # PHP
    ".php":     {"lang": Language.PHP,      "name": "PHP",             "framework": "PHPUnit"},

    # Solidity
    ".sol":     {"lang": Language.SOL,      "name": "Solidity",        "framework": "Hardhat / Foundry"},

    # Markdown / RST (doc-driven test context)
    ".md":      {"lang": Language.MARKDOWN, "name": "Markdown",        "framework": "N/A"},
    ".mdx":     {"lang": Language.MARKDOWN, "name": "Markdown",        "framework": "N/A"},
    ".rst":     {"lang": Language.RST,      "name": "RST",             "framework": "N/A"},

    # HTML / CSS
    ".html":    {"lang": Language.HTML,     "name": "HTML",            "framework": "Selenium / Playwright"},
    ".htm":     {"lang": Language.HTML,     "name": "HTML",            "framework": "Selenium / Playwright"},

    # Protocol Buffers
    ".proto":   {"lang": Language.PROTO,    "name": "Protobuf",        "framework": "N/A"},

    # Haskell
    ".hs":      {"lang": Language.HASKELL,  "name": "Haskell",         "framework": "HSpec"},
    ".lhs":     {"lang": Language.HASKELL,  "name": "Haskell",         "framework": "HSpec"},

    # Elixir
    ".ex":      {"lang": Language.ELIXIR,   "name": "Elixir",          "framework": "ExUnit"},
    ".exs":     {"lang": Language.ELIXIR,   "name": "Elixir",          "framework": "ExUnit"},

    # Lua
    ".lua":     {"lang": Language.LUA,      "name": "Lua",             "framework": "busted"},

    # Perl
    ".pl":      {"lang": Language.PERL,     "name": "Perl",            "framework": "Test::More"},
    ".pm":      {"lang": Language.PERL,     "name": "Perl",            "framework": "Test::More"},
}

# ---------------------------------------------------------------------------
# Languages WITHOUT a dedicated LangChain splitter — generic chunking
# ---------------------------------------------------------------------------
GENERIC_EXTENSION_MAP = {
    # C#
    ".cs":      {"name": "C#",              "framework": "xUnit / NUnit / MSTest"},

    # R
    ".r":       {"name": "R",               "framework": "testthat"},

    # Shell / Bash
    ".sh":      {"name": "Shell",           "framework": "BATS"},
    ".bash":    {"name": "Shell",           "framework": "BATS"},
    ".zsh":     {"name": "Shell",           "framework": "BATS"},
    ".fish":    {"name": "Fish Shell",      "framework": "BATS"},

    # PowerShell
    ".ps1":     {"name": "PowerShell",      "framework": "Pester"},
    ".psm1":    {"name": "PowerShell",      "framework": "Pester"},

    # Dart / Flutter
    ".dart":    {"name": "Dart",            "framework": "flutter_test"},

    # YAML / TOML / JSON (config / IaC testing context)
    ".yaml":    {"name": "YAML",            "framework": "N/A"},
    ".yml":     {"name": "YAML",            "framework": "N/A"},
    ".toml":    {"name": "TOML",            "framework": "N/A"},
    ".json":    {"name": "JSON",            "framework": "N/A"},

    # SQL
    ".sql":     {"name": "SQL",             "framework": "pgTAP / SQLTest"},

    # COBOL
    ".cob":     {"name": "COBOL",           "framework": "COBOL-Unit-Test"},
    ".cbl":     {"name": "COBOL",           "framework": "COBOL-Unit-Test"},

    # Fortran
    ".f90":     {"name": "Fortran",         "framework": "pFUnit"},
    ".f95":     {"name": "Fortran",         "framework": "pFUnit"},
    ".f":       {"name": "Fortran",         "framework": "pFUnit"},

    # MATLAB / Octave
    ".m":       {"name": "MATLAB/Octave",   "framework": "MOxUnit"},

    # Julia
    ".jl":      {"name": "Julia",           "framework": "Test.jl"},

    # Groovy
    ".groovy":  {"name": "Groovy",          "framework": "Spock"},

    # Terraform / HCL
    ".tf":      {"name": "Terraform/HCL",   "framework": "Terratest"},
    ".hcl":     {"name": "HCL",             "framework": "Terratest"},

    # Assembly
    ".asm":     {"name": "Assembly",        "framework": "N/A"},
    ".s":       {"name": "Assembly",        "framework": "N/A"},

    # Objective-C
    ".m":       {"name": "Objective-C",     "framework": "XCTest"},
    ".mm":      {"name": "Objective-C++",   "framework": "XCTest"},

    # Erlang
    ".erl":     {"name": "Erlang",          "framework": "EUnit"},
    ".hrl":     {"name": "Erlang",          "framework": "EUnit"},

    # Clojure
    ".clj":     {"name": "Clojure",         "framework": "clojure.test"},
    ".cljs":    {"name": "ClojureScript",   "framework": "cljs.test"},

    # F#
    ".fs":      {"name": "F#",              "framework": "xUnit / NUnit"},
    ".fsx":     {"name": "F#",              "framework": "xUnit / NUnit"},

    # OCaml
    ".ml":      {"name": "OCaml",           "framework": "Alcotest"},
    ".mli":     {"name": "OCaml",           "framework": "Alcotest"},

    # Crystal
    ".cr":      {"name": "Crystal",         "framework": "Spec"},

    # Zig
    ".zig":     {"name": "Zig",             "framework": "std.testing"},

    # Nim
    ".nim":     {"name": "Nim",             "framework": "unittest"},

    # D
    ".d":       {"name": "D",               "framework": "unittest"},

    # VHDL / Verilog (HDL)
    ".vhd":     {"name": "VHDL",            "framework": "OSVVM"},
    ".vhdl":    {"name": "VHDL",            "framework": "OSVVM"},
    ".v":       {"name": "Verilog",         "framework": "cocotb"},
    ".sv":      {"name": "SystemVerilog",   "framework": "cocotb"},

    # CSS / SCSS / LESS (style sheets)
    ".css":     {"name": "CSS",             "framework": "N/A"},
    ".scss":    {"name": "SCSS",            "framework": "N/A"},
    ".sass":    {"name": "Sass",            "framework": "N/A"},
    ".less":    {"name": "Less",            "framework": "N/A"},
}


def process_and_store_codebase(repo_path: str) -> tuple["Chroma", str]:
    """Chunk, embed, and persist an entire codebase.

    Each repo gets its own isolated Chroma collection + subdirectory so that
    multiple users / repos never share or pollute each other's data.

    Returns:
        (vectorstore, repo_id) — callers should store repo_id so they can
        reload or query the correct collection later via load_vectorstore().
    """
    # ------------------------------------------------------------------ #
    # Derive a stable, unique ID from the repo path                       #
    # ------------------------------------------------------------------ #
    repo_id = make_repo_id(repo_path)
    persist_dir = os.path.join(CHROMA_BASE_DIR, repo_id)
    os.makedirs(persist_dir, exist_ok=True)

    print(f"Repo ID : {repo_id}")
    print(f"Persist : {persist_dir}")

    embeddings = _get_embeddings()
    vectorstore = Chroma(
        collection_name=repo_id,          # ← isolated per repo
        embedding_function=embeddings,
        persist_directory=persist_dir,    # ← isolated subdirectory
    )

    documents = []
    ids       = []
    skipped = 0

    for root, _, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            file_path = os.path.join(root, file)

            # ----------------------------------------------------------------
            # Choose splitter strategy
            # ----------------------------------------------------------------
            if ext in EXTENSION_MAP:
                lang_info = EXTENSION_MAP[ext]
                use_generic = False
            elif ext in GENERIC_EXTENSION_MAP:
                lang_info = GENERIC_EXTENSION_MAP[ext]
                use_generic = True
            else:
                # Unsupported extension — skip silently
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                # ---- Function / class -level chunking --------------------
                for chunk_text, unit_meta in _chunk_by_units(
                    content, ext, lang_info, use_generic
                ):
                    # Stable, deterministic ID → Chroma upserts instead of
                    # duplicating on every re-run of the same repo.
                    doc_id = hashlib.md5(
                        (
                            file_path
                            + unit_meta.get("unit_name", "")
                            + str(unit_meta.get("start_line", ""))
                        ).encode()
                    ).hexdigest()

                    doc = Document(
                        page_content=chunk_text,
                        metadata={
                            # --- file-level context ---
                            "file_path":      file_path,
                            "language":       lang_info["name"],
                            "test_framework": lang_info["framework"],
                            "extension":      ext,
                            "is_test_file":   "test" in file_path.lower(),
                            # --- unit-level context (from _chunk_by_units) ---
                            **unit_meta,
                        },
                    )
                    documents.append(doc)
                    ids.append(doc_id)

            except Exception as e:
                print(f"Skipping {file_path} due to error: {e}")
                skipped += 1

    print(
        f"Created {len(documents)} chunks across "
        f"{len(EXTENSION_MAP) + len(GENERIC_EXTENSION_MAP)} supported extensions "
        f"({skipped} file(s) skipped). Saving to database..."
    )

    if documents:
        # Safe upsert: delete stale entries by ID before re-inserting so that
        # re-running on the same repo never accumulates duplicate vectors.
        try:
            vectorstore.delete(ids=ids)
        except Exception as e:
            logger.debug("delete() before add_documents skipped: %s", e)
        vectorstore.add_documents(documents, ids=ids)

        # Explicitly persist to disk.
        # Chroma >= 0.4.x auto-persists when persist_directory is set, but
        # calling persist() is safe and ensures compatibility with older versions.
        try:
            vectorstore.persist()
            print("Vectorstore persisted to disk successfully.")
        except AttributeError:
            # Newer Chroma versions removed the method; auto-persist is active.
            print("Chroma auto-persist is active (persist_directory set). DB saved.")

    print(f"Done! Database is ready. (repo_id={repo_id})")
    return vectorstore, repo_id


# ---------------------------------------------------------------------------
# DIFF-DRIVEN GENERATION PIPELINE
# ---------------------------------------------------------------------------

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

    print(f"[run_diff_pipeline] {len(supported_files)} supported file(s) changed.")

    results: list[dict] = []

    for rel_path in supported_files:
        abs_path = os.path.join(repo_path, rel_path)
        hunks = get_function_diff(repo_path, rel_path)

        if not hunks:
            print(f"  └─ {rel_path}: no hunks found, skipping.")
            continue

        print(f"  └─ {rel_path}: {len(hunks)} hunk(s) found.")

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

    print(f"[run_diff_pipeline] Generated {len(results)} prompt(s).")
    return results

# ---------------------------------------------------------------------------
# Incremental processing — only re-embed files changed since last commit
# ---------------------------------------------------------------------------

def process_changed_files(repo_path: str) -> list[str]:
    """Return a filtered list of files that changed in the last commit
    AND have a supported extension (EXTENSION_MAP or GENERIC_EXTENSION_MAP).

    Useful for incremental re-indexing: instead of re-processing the entire
    repo, only update the embeddings for files that actually changed.

    Args:
        repo_path: Absolute or relative path to the git repository root.

    Returns:
        List of file paths (strings) that are both changed and supported.
        Returns an empty list if no supported files changed.
    """
    all_supported_exts = set(EXTENSION_MAP.keys()) | set(GENERIC_EXTENSION_MAP.keys())

    changed_files = get_changed_files(repo_path)

    supported_changed = [
        f for f in changed_files
        if f.strip()  # skip empty lines produced by git diff
        and os.path.splitext(f)[1].lower() in all_supported_exts
    ]

    print(
        f"[process_changed_files] {len(changed_files)} file(s) changed in last commit, "
        f"{len(supported_changed)} with supported extension(s)."
    )
    return supported_changed


# ---------------------------------------------------------------------------
# Helper: delete all stored chunks that belong to a specific file
# ---------------------------------------------------------------------------

def delete_chunks_for_file(file_path: str, vectorstore) -> int:
    """Delete every embedding chunk whose ``file_path`` metadata matches *file_path*.

    Args:
        file_path:   Absolute path of the file whose chunks should be removed.
        vectorstore: Open Chroma collection for the repo.

    Returns:
        Number of chunks deleted (0 if none found or on error).
    """
    try:
        results = vectorstore.get(where={"file_path": file_path})
        ids_to_delete = results.get("ids", [])
        if ids_to_delete:
            vectorstore.delete(ids=ids_to_delete)
            logger.info("[delete_chunks_for_file] Deleted %d chunk(s) for %s",
                        len(ids_to_delete), file_path)
        return len(ids_to_delete)
    except Exception as e:
        logger.warning("[delete_chunks_for_file] Error deleting chunks for %s: %s",
                       file_path, e)
        return 0


# ---------------------------------------------------------------------------
# Incremental indexing: re-embed only files changed since last commit
# ---------------------------------------------------------------------------

def update_vectorstore(repo_path: str, repo_id: str) -> tuple["Chroma", int]:
    """Incrementally update embeddings for files changed in the last git commit.

    Only processes files returned by process_changed_files(), making this
    dramatically faster than a full re-index for large repositories.

    Flow per changed file:
        1. Delete existing chunks (by metadata filter on file_path)
        2. Re-chunk the file at function/class level
        3. Compute deterministic IDs
        4. Safe-upsert via delete(ids) + add_documents(ids=ids)

    Args:
        repo_path: Absolute path to the git repository root.
        repo_id:   ID returned by process_and_store_codebase().

    Returns:
        (vectorstore, total_chunks_added)
    """
    vectorstore = load_vectorstore(repo_id)
    changed_files = process_changed_files(repo_path)

    if not changed_files:
        logger.info("[update_vectorstore] No supported files changed. Nothing to do.")
        return vectorstore, 0

    total_added = 0

    for rel_path in changed_files:
        abs_path = os.path.join(repo_path, rel_path)
        ext = os.path.splitext(rel_path)[1].lower()

        if ext in EXTENSION_MAP:
            lang_info = EXTENSION_MAP[ext]
            use_generic = False
        elif ext in GENERIC_EXTENSION_MAP:
            lang_info = GENERIC_EXTENSION_MAP[ext]
            use_generic = True
        else:
            continue

        logger.info("[update_vectorstore] Processing changed file: %s", rel_path)

        # Step 1 — remove all stale chunks for this file
        deleted = delete_chunks_for_file(abs_path, vectorstore)
        logger.info("  Deleted %d stale chunk(s).", deleted)

        # Step 2 — re-chunk and re-embed
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            documents: list[Document] = []
            ids: list[str] = []

            for chunk_text, unit_meta in _chunk_by_units(
                content, ext, lang_info, use_generic
            ):
                doc_id = hashlib.md5(
                    (
                        abs_path
                        + unit_meta.get("unit_name", "")
                        + str(unit_meta.get("start_line", ""))
                    ).encode()
                ).hexdigest()

                doc = Document(
                    page_content=chunk_text,
                    metadata={
                        "file_path":      abs_path,
                        "language":       lang_info["name"],
                        "test_framework": lang_info["framework"],
                        "extension":      ext,
                        "is_test_file":   "test" in rel_path.lower(),
                        **unit_meta,
                    },
                )
                documents.append(doc)
                ids.append(doc_id)

            if documents:
                # Safe upsert
                try:
                    vectorstore.delete(ids=ids)
                except Exception:
                    pass
                vectorstore.add_documents(documents, ids=ids)
                total_added += len(documents)
                logger.info("  Inserted %d chunk(s) for %s.", len(documents), rel_path)

        except Exception as e:
            logger.error("[update_vectorstore] Skipping %s: %s", rel_path, e)

    # Persist
    try:
        vectorstore.persist()
    except AttributeError:
        pass  # Chroma >= 0.4 auto-persists

    logger.info(
        "[update_vectorstore] Done. %d chunk(s) added/updated across %d file(s).",
        total_added, len(changed_files),
    )
    return vectorstore, total_added