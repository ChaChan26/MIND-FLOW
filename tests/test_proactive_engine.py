"""
Comprehensive Unit Tests for the Proactive Cognitive Companion Engine.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import time
import unittest
from collections import deque

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_base import BaseMindFlowTestCase
from app import evaluate_proactive_nudges
from backend.server import shared_state, SHARED_API_TOKEN


class TestProactiveEngine(BaseMindFlowTestCase):
    def setUp(self):
        super().setUp()
        self.nudge_state = {
            "last_nudges": {},
            "distraction_dwell_start": None,
            "active_work_seconds": 0,
            "active_hydration_seconds": 0,
            "manual_override_until": 0.0
        }
        self.context_switch_deque = deque(maxlen=30)
        shared_state["active_nudge"] = None
        shared_state["nudge_snooze_until"] = 0.0
        shared_state["session_extension_seconds"] = 0
        shared_state["current_mode"] = "work"
        shared_state["mode"] = "work"
        shared_state["timer_seconds"] = 600

    def test_low_battery_critical_nudge(self):
        """Battery <= 15% during work mode should trigger a critical recharge nudge."""
        settings = {"proactivity_level": "balanced", "enable_desktop_toasts": False, "enable_audio_chimes": False}
        evaluate_proactive_nudges(
            current_mode="work",
            target_mode="work",
            active_process="Code.exe",
            active_title="project - Visual Studio Code",
            elapsed_seconds=300,
            work_limit_sec=1500,
            battery_cap=12.0,
            is_flow_session=False,
            idle_sec_val=0,
            settings=settings,
            context_switch_deque=self.context_switch_deque,
            nudge_state=self.nudge_state,
            shared_state=shared_state
        )
        self.assertIsNotNone(shared_state["active_nudge"])
        self.assertEqual(shared_state["active_nudge"]["type"], "critical")
        self.assertIn("Critical Stamina", shared_state["active_nudge"]["title"])

    def test_sprint_complete_nudge(self):
        """Reaching the work limit triggers a sprint complete nudge."""
        settings = {"proactivity_level": "balanced", "enable_desktop_toasts": False, "enable_audio_chimes": False}
        evaluate_proactive_nudges(
            current_mode="work",
            target_mode="work",
            active_process="Code.exe",
            active_title="project - Code",
            elapsed_seconds=1550,
            work_limit_sec=1500,
            battery_cap=60.0,
            is_flow_session=False,
            idle_sec_val=0,
            settings=settings,
            context_switch_deque=self.context_switch_deque,
            nudge_state=self.nudge_state,
            shared_state=shared_state
        )
        self.assertIsNotNone(shared_state["active_nudge"])
        self.assertEqual(shared_state["active_nudge"]["type"], "info")
        self.assertIn("Focus Sprint Complete", shared_state["active_nudge"]["title"])

    def test_flow_state_suppresses_non_critical_nudges(self):
        """When in flow, low battery (30%) and sprint complete nudges should be suppressed."""
        settings = {"proactivity_level": "balanced", "enable_desktop_toasts": False, "enable_audio_chimes": False}
        evaluate_proactive_nudges(
            current_mode="work",
            target_mode="work",
            active_process="Code.exe",
            active_title="project - Code",
            elapsed_seconds=1600,
            work_limit_sec=1500,
            battery_cap=25.0,
            is_flow_session=True,  # IN FLOW
            idle_sec_val=0,
            settings=settings,
            context_switch_deque=self.context_switch_deque,
            nudge_state=self.nudge_state,
            shared_state=shared_state
        )
        self.assertIsNone(shared_state["active_nudge"])

    def test_flow_state_allows_critical_stamina_nudge(self):
        """Even in flow state, critically low battery (<15%) MUST break through."""
        settings = {"proactivity_level": "balanced", "enable_desktop_toasts": False, "enable_audio_chimes": False}
        evaluate_proactive_nudges(
            current_mode="work",
            target_mode="work",
            active_process="Code.exe",
            active_title="project - Code",
            elapsed_seconds=1600,
            work_limit_sec=1500,
            battery_cap=10.0,
            is_flow_session=True,  # IN FLOW
            idle_sec_val=0,
            settings=settings,
            context_switch_deque=self.context_switch_deque,
            nudge_state=self.nudge_state,
            shared_state=shared_state
        )
        self.assertIsNotNone(shared_state["active_nudge"])
        self.assertEqual(shared_state["active_nudge"]["type"], "critical")

    def test_distraction_drift_with_dwell_period(self):
        """Recharge apps during work sprints trigger a distraction nudge only after the dwell period (30s)."""
        settings = {"proactivity_level": "balanced", "enable_distraction_nudges": True, "enable_desktop_toasts": False, "enable_audio_chimes": False}
        
        # Tick 1: Dwell starts
        evaluate_proactive_nudges(
            current_mode="work",
            target_mode="recharge",
            active_process="youtube.exe",
            active_title="YouTube - Cat Videos",
            elapsed_seconds=300,
            work_limit_sec=1500,
            battery_cap=80.0,
            is_flow_session=False,
            idle_sec_val=0,
            settings=settings,
            context_switch_deque=self.context_switch_deque,
            nudge_state=self.nudge_state,
            shared_state=shared_state
        )
        self.assertIsNone(shared_state["active_nudge"])
        self.assertIsNotNone(self.nudge_state["distraction_dwell_start"])

        # Tick 2: Dwell expired (simulate 35s passed)
        self.nudge_state["distraction_dwell_start"] = time.time() - 35.0
        evaluate_proactive_nudges(
            current_mode="work",
            target_mode="recharge",
            active_process="youtube.exe",
            active_title="YouTube - Cat Videos",
            elapsed_seconds=335,
            work_limit_sec=1500,
            battery_cap=80.0,
            is_flow_session=False,
            idle_sec_val=0,
            settings=settings,
            context_switch_deque=self.context_switch_deque,
            nudge_state=self.nudge_state,
            shared_state=shared_state
        )
        self.assertIsNotNone(shared_state["active_nudge"])
        self.assertIn("Distraction Drift", shared_state["active_nudge"]["title"])

    def test_context_switch_thrashing_nudge(self):
        """Rapid window switching (>5 switches in 2 mins) triggers a cognitive friction warning."""
        settings = {"proactivity_level": "balanced", "enable_thrashing_nudges": True, "enable_desktop_toasts": False, "enable_audio_chimes": False}
        
        now = time.time()
        for i in range(6):
            self.context_switch_deque.append(now - (i * 10))  # 6 switches within 60s
            
        evaluate_proactive_nudges(
            current_mode="work",
            target_mode="work",
            active_process="Code.exe",
            active_title="project - Code",
            elapsed_seconds=300,
            work_limit_sec=1500,
            battery_cap=75.0,
            is_flow_session=False,
            idle_sec_val=0,
            settings=settings,
            context_switch_deque=self.context_switch_deque,
            nudge_state=self.nudge_state,
            shared_state=shared_state
        )
        self.assertIsNotNone(shared_state["active_nudge"])
        self.assertIn("High Cognitive Friction Detected", shared_state["active_nudge"]["title"])

    def test_disabled_proactivity_stance(self):
        """When proactivity is disabled, no nudges should ever fire."""
        settings = {"proactivity_level": "disabled"}
        evaluate_proactive_nudges(
            current_mode="work",
            target_mode="work",
            active_process="Code.exe",
            active_title="project - Code",
            elapsed_seconds=2000,
            work_limit_sec=1500,
            battery_cap=5.0,  # Critical
            is_flow_session=False,
            idle_sec_val=0,
            settings=settings,
            context_switch_deque=self.context_switch_deque,
            nudge_state=self.nudge_state,
            shared_state=shared_state
        )
        self.assertIsNone(shared_state["active_nudge"])

    def test_snooze_functionality(self):
        """Snoozing suppresses non-critical nudges for the snooze duration."""
        settings = {"proactivity_level": "balanced"}
        shared_state["nudge_snooze_until"] = time.time() + 900.0  # Snoozed 15 mins
        
        evaluate_proactive_nudges(
            current_mode="work",
            target_mode="work",
            active_process="Code.exe",
            active_title="project - Code",
            elapsed_seconds=1600,
            work_limit_sec=1500,
            battery_cap=25.0,  # Warning level, not critical
            is_flow_session=False,
            idle_sec_val=0,
            settings=settings,
            context_switch_deque=self.context_switch_deque,
            nudge_state=self.nudge_state,
            shared_state=shared_state
        )
        self.assertIsNone(shared_state["active_nudge"])

    def test_nudge_actions_api_extend(self):
        """Testing the POST /api/nudge/action endpoint for extend_5m."""
        shared_state["session_extension_seconds"] = 0
        resp = self.client.post("/api/nudge/action", json={"action": "extend_5m"}, headers=self.valid_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(shared_state["session_extension_seconds"], 300)

    def test_nudge_actions_api_take_break(self):
        """Testing the POST /api/nudge/action endpoint for take_break (switches mode)."""
        resp = self.client.post("/api/nudge/action", json={"action": "take_break"}, headers=self.valid_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(shared_state["current_mode"], "rest")

    def test_nudge_actions_api_snooze(self):
        """Testing the POST /api/nudge/action endpoint for snooze."""
        before = time.time()
        resp = self.client.post("/api/nudge/action", json={"action": "snooze"}, headers=self.valid_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(shared_state["nudge_snooze_until"], before + 890.0)

    def test_database_settings_schema(self):
        """Test that MindFlowDB initializes with proactivity defaults and persists updates."""
        settings = self.db.get_settings()
        self.assertIn("proactivity_level", settings)
        self.assertIn("enable_desktop_toasts", settings)
        self.assertIn("enable_audio_chimes", settings)

        # Update settings with alias
        orig_level = settings.get("proactivity_level", "balanced")
        try:
            self.db.update_settings({"proactivity_level": "strict", "enable_audio_chimes": 0, "enable_eye_care_nudges": False})
            updated = self.db.get_settings()
            self.assertEqual(updated.get("proactivity_level"), "strict")
            self.assertEqual(updated.get("enable_audio_chimes"), False)
            self.assertEqual(updated.get("enable_eyecare_nudges"), False)
        finally:
            self.db.update_settings({"proactivity_level": orig_level, "enable_audio_chimes": True, "enable_eyecare_nudges": True})

    def test_distraction_dwell_cancelled_on_work_return(self):
        """Returning to work mode cancels the distraction dwell timer."""
        settings = {"proactivity_level": "balanced", "enable_distraction_nudges": True}
        self.nudge_state["distraction_dwell_start"] = time.time() - 10.0
        
        evaluate_proactive_nudges(
            current_mode="work",
            target_mode="work",
            active_process="Code.exe",
            active_title="project - Code",
            elapsed_seconds=300,
            work_limit_sec=1500,
            battery_cap=80.0,
            is_flow_session=False,
            idle_sec_val=0,
            settings=settings,
            context_switch_deque=self.context_switch_deque,
            nudge_state=self.nudge_state,
            shared_state=shared_state
        )
        self.assertIsNone(self.nudge_state["distraction_dwell_start"])

    def test_extension_seconds_capped_at_1800(self):
        """Testing that extend_5m action caps session extension at 1800 seconds."""
        shared_state["session_extension_seconds"] = 1700
        resp = self.client.post("/api/nudge/action", json={"action": "extend_5m"}, headers=self.valid_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(shared_state["session_extension_seconds"], 1800)


if __name__ == "__main__":
    unittest.main()
