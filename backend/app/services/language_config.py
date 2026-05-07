from langchain_text_splitters import Language

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
