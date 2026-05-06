import ast
import re
from typing import Generator
from langchain_text_splitters import RecursiveCharacterTextSplitter

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
