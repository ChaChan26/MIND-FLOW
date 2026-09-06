"""
Centralized thread pool management for MIND-FLOW background tasks.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

workspace_executor = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="mindflow-workspace"
)

def shutdown_all(wait: bool = False):
    """Cleanly shutdown all shared thread pools."""
    try:
        workspace_executor.shutdown(wait=wait)
    except Exception as e:
        logger.debug("Error shutting down workspace_executor: %s", e)

