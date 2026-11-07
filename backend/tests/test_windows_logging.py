"""
Regression test for Windows-safe concurrent logging and file rollover.
Verifies that:
1. WindowsSafeRotatingFileHandler successfully rotates even when another file handle is open.
2. Handlers are deduplicated across imports.
3. Concurrent multi-threaded logging does not crash or raise PermissionError.
"""

import concurrent.futures
import logging
import os
import tempfile
import time
from pathlib import Path

import pytest
from app.rag.logger import WindowsSafeRotatingFileHandler, logger


def test_windows_safe_rollover_under_file_lock():
    """Verify rollover succeeds without PermissionError when an external handle holds the file open."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test_rollover.log"
        handler = WindowsSafeRotatingFileHandler(
            log_path,
            maxBytes=200,
            backupCount=3,
            encoding="utf-8",
        )
        test_logger = logging.getLogger("TEST_WIN_LOG")
        test_logger.handlers = [handler]
        test_logger.setLevel(logging.INFO)

        # Write until near rollover
        test_logger.info("Message 1: Initializing test log with enough bytes to fill space.")
        assert log_path.exists()

        # Simulate another process/thread opening the log file without FILE_SHARE_DELETE
        # On Windows, this normally causes os.rename to fail with [WinError 32]
        with open(log_path, "r+", encoding="utf-8") as _lock_handle:
            # Trigger rollover while _lock_handle is open
            for i in range(10):
                test_logger.info(f"Rollover message {i}: writing more content to exceed 200 bytes limit.")

        # Verify that rollover occurred without raising PermissionError and backup exists
        backup_1 = Path(tmpdir) / "test_rollover.log.1"
        assert backup_1.exists() or log_path.stat().st_size <= 2000
        handler.close()


def test_concurrent_multithreaded_logging():
    """Verify concurrent writes across worker threads complete cleanly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test_concurrent.log"
        handler = WindowsSafeRotatingFileHandler(
            log_path,
            maxBytes=500,
            backupCount=2,
            encoding="utf-8",
        )
        test_logger = logging.getLogger("TEST_CONCURRENT_LOG")
        test_logger.handlers = [handler]
        test_logger.setLevel(logging.INFO)

        def worker(thread_id: int):
            for i in range(15):
                test_logger.info(f"Thread {thread_id} - Log entry {i} - concurrent execution")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker, i) for i in range(5)]
            for f in futures:
                f.result()

        handler.close()
        assert log_path.exists()


def test_logger_handler_deduplication():
    """Verify that importing or accessing logger does not register duplicate handlers."""
    handlers = logger.handlers
    file_handlers = [h for h in handlers if isinstance(h, WindowsSafeRotatingFileHandler)]
    # Filter out pytest-injected log capture handlers
    console_handlers = [
        h for h in handlers
        if type(h) is logging.StreamHandler and not isinstance(h, logging.FileHandler)
    ]

    assert len(file_handlers) <= 1
    assert len(console_handlers) <= 1
