"""
Project UNKNOWN (AETHER)

Central logging configuration.
All project modules should import this logger.
"""

import logging
from logging.handlers import RotatingFileHandler

from app.rag.config import settings

# Log file location
LOG_FILE = settings.LOG_DIR / "unknown.log"

# Create logger
logger = logging.getLogger("UNKNOWN")
logger.setLevel(logging.INFO)

# Avoid duplicate handlers when imported multiple times
if not logger.handlers:

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File logging
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=2_000_000,
        backupCount=5,
        encoding=settings.DEFAULT_ENCODING,
    )
    file_handler.setFormatter(formatter)

    # Console logging
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Prevent duplicate logs from root logger
    logger.propagate = False