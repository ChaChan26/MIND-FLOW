"""
Mode Transition Engine managing session state transitions, flow duration logging,
and workspace profile swapping with serial background execution.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

from datetime import datetime, timedelta
import logging
from backend.thread_pools import workspace_executor

logger = logging.getLogger(__name__)

class ModeTransitionEngine:
    def __init__(self, db, shared_state, nudge_state, workspace_mgr=None):
        self.db = db
        self.shared_state = shared_state
        self.nudge_state = nudge_state
        self.workspace_mgr = workspace_mgr
        self._workspace_executor = workspace_executor

    def shutdown(self, wait: bool = False):
        """Cleanly shutdown the workspace executor."""
        from backend.thread_pools import shutdown_all
        shutdown_all(wait=wait)

    def execute_mode_transition(
        self,
        prev_mode: str,
        new_mode: str,
        state_start_time: datetime,
        is_flow_session: bool,
        flow_start_time: datetime | None,
        idle_limit: int,
        is_idle_transition: bool,
        battery=None
    ):
        """Execute a mode transition: log the ending session, reset timers, swap workspace files.

        Returns:
            tuple: (new_current_mode, new_state_start_time, is_flow_session, flow_start_time, work_consecutive_seconds)
        """
        now = datetime.now()

        # Calculate flow state for ending work session
        is_flow = False
        flow_dur = 0.0
        if prev_mode == "work" and is_flow_session:
            is_flow = True
            work_end = now
            if is_idle_transition and flow_start_time:
                work_end = max(state_start_time, now - timedelta(seconds=idle_limit))
            if flow_start_time:
                flow_dur = max(0.0, (work_end - flow_start_time).total_seconds())

        # Log the ending session (backdate if idle-triggered rest)
        if is_idle_transition and prev_mode in ["work", "recharge", "neutral"]:
            transition_time = max(state_start_time, now - timedelta(seconds=idle_limit))
            self.db.log_session(prev_mode, state_start_time, transition_time, is_flow=is_flow, flow_duration=flow_dur, wait=False)
            state_start_time = transition_time
        else:
            self.db.log_session(prev_mode, state_start_time, now, is_flow=is_flow, flow_duration=flow_dur, wait=False)
            state_start_time = now

        # Update shared state
        self.shared_state["mode_start_time"] = state_start_time
        self.shared_state["session_extension_seconds"] = 0
        self.shared_state["current_mode"] = new_mode
        self.shared_state["elapsed_seconds"] = 0

        # Reset accumulators when leaving work
        if new_mode in ["rest", "recharge"]:
            self.nudge_state["active_work_seconds"] = 0

        self.nudge_state["distraction_dwell_start"] = None

        # Swap workspace files asynchronously and serially
        if self.workspace_mgr:
            try:
                self._workspace_executor.submit(
                    self.workspace_mgr.transition_workspace,
                    prev_mode,
                    new_mode
                )
            except Exception as e:
                logger.exception(f"Error transitioning workspace: {e}")

        return new_mode, state_start_time, False, None, 0
