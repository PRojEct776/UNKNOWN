"""
Project UNKNOWN (AETHER)

Central logging configuration.
All project modules should import this logger.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.rag.config import settings

# Log file location
LOG_FILE = settings.LOG_DIR / "unknown.log"
LOCK_FILE = settings.LOG_DIR / ".unknown_log_rotation.lock"


class WindowsSafeRotatingFileHandler(RotatingFileHandler):
    """
    Multiprocess- and Windows-safe RotatingFileHandler.

    Standard RotatingFileHandler fails on Windows with:
    PermissionError: [WinError 32] The process cannot access the file because it is being used by another process.
    This occurs because on Windows, os.rename() fails if any process holds an open handle
    to the file without FILE_SHARE_DELETE.

    This handler:
    1. Uses an inter-process file lock (via filelock) to coordinate rotation across processes.
    2. Flushes and closes the stream before attempting rollover.
    3. Re-checks file size after acquiring lock in case another process already rotated.
    4. Retries os.rename() with exponential backoff.
    5. If rename is blocked by Windows file locking (PermissionError), falls back to copy-and-truncate,
       guaranteeing that log rotation never crashes an active request and logs are preserved.
    """

    def __init__(
        self,
        filename: str | Path,
        mode: str = "a",
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: str | None = None,
        delay: bool = False,
    ) -> None:
        super().__init__(
            str(filename),
            mode=mode,
            maxBytes=maxBytes,
            backupCount=backupCount,
            encoding=encoding,
            delay=delay,
        )
        self._rotation_lock = threading.Lock()

    def doRollover(self) -> None:
        with self._rotation_lock:
            lock = None
            try:
                import filelock

                lock = filelock.FileLock(str(LOCK_FILE), timeout=2.0)
                lock.acquire()
            except Exception:
                pass

            try:
                # Flush and close stream before attempting rotation
                if self.stream:
                    try:
                        self.stream.flush()
                    except Exception:
                        pass
                    self.stream.close()
                    self.stream = None

                # Re-check file size; another process may have rotated while waiting for lock
                try:
                    if os.path.exists(self.baseFilename) and os.path.getsize(self.baseFilename) < self.maxBytes:
                        if not self.delay:
                            self.stream = self._open()
                        return
                except Exception:
                    pass

                if self.backupCount > 0:
                    for i in range(self.backupCount - 1, 0, -1):
                        sfn = self.rotation_filename(f"{self.baseFilename}.{i}")
                        dfn = self.rotation_filename(f"{self.baseFilename}.{i + 1}")
                        if os.path.exists(sfn):
                            if os.path.exists(dfn):
                                try:
                                    os.remove(dfn)
                                except Exception:
                                    pass
                            try:
                                os.rename(sfn, dfn)
                            except Exception:
                                pass

                    dfn = self.rotation_filename(f"{self.baseFilename}.1")
                    if os.path.exists(dfn):
                        try:
                            os.remove(dfn)
                        except Exception:
                            pass

                    # Attempt standard rename with retries
                    renamed = False
                    for attempt in range(5):
                        try:
                            self.rotate(self.baseFilename, dfn)
                            renamed = True
                            break
                        except (PermissionError, OSError):
                            time.sleep(0.04 * (attempt + 1))

                    # If rename is blocked by Windows file lock, perform safe copy-and-truncate
                    if not renamed and os.path.exists(self.baseFilename):
                        try:
                            shutil.copy2(self.baseFilename, dfn)
                            with open(
                                self.baseFilename,
                                "r+",
                                encoding=self.encoding or settings.DEFAULT_ENCODING,
                            ) as f:
                                f.truncate(0)
                        except Exception:
                            # In extreme lock scenarios, process continues without crash
                            pass

                if not self.delay:
                    self.stream = self._open()
            finally:
                if lock is not None:
                    try:
                        lock.release()
                    except Exception:
                        pass


# Create logger
logger = logging.getLogger("UNKNOWN")
logger.setLevel(logging.INFO)

# Avoid duplicate handlers when imported multiple times or from different packages
has_file_handler = any(
    isinstance(h, (RotatingFileHandler, logging.FileHandler))
    for h in logger.handlers
)
has_console_handler = any(
    isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
    for h in logger.handlers
)

formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

if not has_file_handler:
    file_handler = WindowsSafeRotatingFileHandler(
        LOG_FILE,
        maxBytes=2_000_000,
        backupCount=5,
        encoding=settings.DEFAULT_ENCODING,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

if not has_console_handler:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# Prevent duplicate logs from root logger
logger.propagate = False
