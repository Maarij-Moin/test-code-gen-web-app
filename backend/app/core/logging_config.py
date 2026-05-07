"""Centralized logging configuration for the FastAPI backend.

Architecture summary:
- A single setup_logging() function configures root logging for the entire app.
- Console + rotating file handlers are attached to the root logger.
- Uvicorn access logs use a dedicated handler to keep noisy request logs separate.
- Duplicate handlers are prevented so reloads do not multiply log lines.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings


_CONFIGURED = False


def _resolve_log_level() -> int:
	"""Resolve the log level from environment and settings.

	Precedence:
		1. LOG_LEVEL environment variable
		2. DEBUG setting (DEBUG -> DEBUG else INFO)
	"""

	env_level = os.getenv("LOG_LEVEL", "").strip().upper()
	if env_level:
		return logging._nameToLevel.get(env_level, logging.INFO)
	return logging.DEBUG if settings.DEBUG else logging.INFO


def _build_formatter() -> logging.Formatter:
	"""Create the standard log formatter used across the app."""

	return logging.Formatter(
		fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
		datefmt="%Y-%m-%dT%H:%M:%S",
	)


def _ensure_logs_dir() -> Path:
	"""Ensure the logs directory exists before file handlers are attached."""

	logs_dir = Path("logs")
	logs_dir.mkdir(parents=True, exist_ok=True)
	return logs_dir


def setup_logging() -> logging.Logger:
	"""Configure structured logging for the entire application.

	Returns:
		The configured root logger instance.
	"""

	global _CONFIGURED
	if _CONFIGURED:
		return logging.getLogger()

	log_level = _resolve_log_level()
	formatter = _build_formatter()
	logs_dir = _ensure_logs_dir()

	# Root logger handles application logs.
	root_logger = logging.getLogger()
	root_logger.setLevel(log_level)

	# Avoid duplicate handlers on reload.
	if root_logger.handlers:
		root_logger.handlers.clear()

	console_handler = logging.StreamHandler()
	console_handler.setLevel(log_level)
	console_handler.setFormatter(formatter)

	file_handler = RotatingFileHandler(
		filename=str(logs_dir / "app.log"),
		maxBytes=10 * 1024 * 1024,
		backupCount=5,
		encoding="utf-8",
	)
	file_handler.setLevel(log_level)
	file_handler.setFormatter(formatter)

	root_logger.addHandler(console_handler)
	root_logger.addHandler(file_handler)

	# Uvicorn access logging: keep access logs separate and prevent duplication.
	access_logger = logging.getLogger("uvicorn.access")
	access_logger.setLevel(logging.INFO)
	access_logger.propagate = False
	access_logger.handlers.clear()

	access_handler = logging.StreamHandler()
	access_handler.setLevel(logging.INFO)
	access_handler.setFormatter(formatter)
	access_logger.addHandler(access_handler)

	# Uvicorn error logger should propagate to root handlers.
	logging.getLogger("uvicorn.error").propagate = True

	_CONFIGURED = True
	root_logger.debug("Logging initialized at level=%s", logging.getLevelName(log_level))
	return root_logger


def get_logger(name: str) -> logging.Logger:
	"""Return a module-level logger with the given name."""

	return logging.getLogger(name)


# Example usage for services/routes:
# from app.core.logging_config import get_logger
# logger = get_logger(__name__)
