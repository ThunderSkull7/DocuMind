"""Logging configuration for DocuMind.

Ensures consistent logging formatting and levels across modules while
preventing accidental logging of sensitive document contents.
"""

import logging
import sys
from typing import TextIO

from documind.config import get_settings

DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    level: str | None = None,
    stream: TextIO | None = None,
) -> logging.Logger:
    """Configure and return the root logger for the DocuMind application."""
    settings = get_settings()
    log_level_name = level or settings.log_level
    numeric_level = getattr(logging, log_level_name.upper(), logging.INFO)

    target_stream = stream or sys.stdout

    root_logger = logging.getLogger("documind")
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers if reconfigured
    if not root_logger.handlers:
        handler = logging.StreamHandler(target_stream)
        handler.setLevel(numeric_level)
        formatter = logging.Formatter(fmt=DEFAULT_FORMAT, datefmt=DATE_FORMAT)
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    else:
        root_logger.setLevel(numeric_level)
        for handler in root_logger.handlers:
            handler.setLevel(numeric_level)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a scoped logger for a specific module or component."""
    if not name.startswith("documind"):
        name = f"documind.{name}"
    return logging.getLogger(name)
