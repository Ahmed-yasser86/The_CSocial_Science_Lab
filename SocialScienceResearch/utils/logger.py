"""Logging helpers for the SocialScienceResearch module.

Mirrors the project convention in ``Ingestion_Pipline/utils/logger.py``:
ANSI/emoji colored console helpers plus a stdlib ``logging`` channel for
structured/debug output.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone


class Colors:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARKCYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


def _safe_print(text: str) -> None:
    """Print without crashing on non-encodable glyphs (e.g. emoji in cp1252).

    Prefers UTF-8 output when the stream supports reconfiguration; otherwise
    falls back to an ASCII-safe rendering of the line.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log_info(message: str, color: str = Colors.CYAN) -> None:
    """Log info message with color."""
    _safe_print(f"{color}ℹ️  [{_timestamp()}] {message}{Colors.END}")


def log_success(message: str) -> None:
    """Log success message in green."""
    _safe_print(f"{Colors.GREEN}✅ [{_timestamp()}] {message}{Colors.END}")


def log_error(message: str) -> None:
    """Log error message in red."""
    _safe_print(f"{Colors.RED}❌ [{_timestamp()}] {message}{Colors.END}")


def log_warning(message: str) -> None:
    """Log warning message in yellow."""
    _safe_print(f"{Colors.YELLOW}⚠️  [{_timestamp()}] {message}{Colors.END}")


def log_header(message: str) -> None:
    """Log header message with emphasis."""
    _safe_print(f"\n{Colors.BOLD}{Colors.PURPLE}{'=' * 60}{Colors.END}")
    _safe_print(f"{Colors.BOLD}{Colors.PURPLE}🚀 {message}{Colors.END}")
    _safe_print(f"{Colors.BOLD}{Colors.PURPLE}{'=' * 60}{Colors.END}\n")


def get_logger(name: str) -> logging.Logger:
    """Return a module-level stdlib logger (project debug convention)."""
    logger = logging.getLogger(name)
    if not logger.handlers and not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    return logger
