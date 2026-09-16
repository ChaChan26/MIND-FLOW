"""
Centralized thread pool management for MIND-FLOW background tasks.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

from concurrent.futures import ThreadPoolExecutor, Future
import logging

logger = logging.getLogger(__name__)

def _log_future_exception(future: Future):
    """Callback to log unhandled exceptions from executor-submitted tasks."""
    try:
        exc = future.exception()
        if exc is not None:
            logger.error("Background task failed with exception: %s", exc, exc_info=exc)
    except Exception:
        pass

workspace_executor = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="mindflow-workspace"
)

def submit_workspace_task(fn, *args, **kwargs) -> Future:
    """Submit a task to workspace_executor with automatic exception logging."""
    future = workspace_executor.submit(fn, *args, **kwargs)
    future.add_done_callback(_log_future_exception)
    return future

def shutdown_all(wait: bool = False):
    """Cleanly shutdown all shared thread pools."""
    try:
        workspace_executor.shutdown(wait=wait)
    except Exception as e:
        logger.debug("Error shutting down workspace_executor: %s", e)
