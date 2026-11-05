"""
Structured Logging Configuration for CYRAXI Platform
Provides consistent formatting and log-level configuration across all modules.
"""

import logging
import os
import sys

_DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
_DEFAULT_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def get_logger(name: str) -> logging.Logger:
    """Return a standard CYRAXI logger instance configured with platform defaults."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(_DEFAULT_FORMAT, datefmt=_DEFAULT_DATE_FORMAT)
        )
        logger.addHandler(handler)

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)

    return logger
