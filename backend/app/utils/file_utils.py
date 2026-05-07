"""Reusable file utilities for the FastAPI backend."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Iterable


logger = logging.getLogger(__name__)


def ensure_directory(path: str | Path) -> Path:
    """Ensure a directory exists, creating it if needed.

    Args:
        path: Directory path to create.

    Returns:
        Resolved Path object for the directory.
    """

    dir_path = Path(path).expanduser()
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured directory exists: %s", dir_path)
    except OSError as exc:
        logger.error("Failed to create directory %s: %s", dir_path, exc)
        raise
    return dir_path.resolve()


def safe_read_file(path: str | Path) -> str:
    """Read a UTF-8 file safely and return its content.

    Args:
        path: File path to read.

    Returns:
        File contents as a string, or an empty string on error.
    """

    file_path = Path(path)
    try:
        content = file_path.read_text(encoding="utf-8")
        logger.debug("Read %d characters from %s", len(content), file_path)
        return content
    except (FileNotFoundError, UnicodeDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", file_path, exc)
        return ""


def get_file_extension(path: str | Path) -> str:
    """Return the lowercase file extension (including leading dot)."""

    return Path(path).suffix.lower()


def is_supported_file(path: str | Path, supported_extensions: Iterable[str]) -> bool:
    """Check whether a file extension is supported.

    Args:
        path: File path to evaluate.
        supported_extensions: Iterable of supported extensions.

    Returns:
        True if the extension is supported.
    """

    ext = get_file_extension(path)
    supported = {e.lower() for e in supported_extensions}
    return ext in supported


def normalize_path(path: str | Path) -> str:
    """Return a canonical normalized absolute path string."""

    return str(Path(path).expanduser().resolve())


def generate_md5(text: str) -> str:
    """Return the MD5 hash of the input text."""

    return hashlib.md5(text.encode("utf-8")).hexdigest()


def generate_sha256(text: str) -> str:
    """Return the SHA256 hash of the input text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()
