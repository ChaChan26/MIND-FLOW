"""
Unit tests for context-switches and session history endpoints with authentication enforcement.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_base import BaseMindFlowTestCase


class TestNewEndpoints(BaseMindFlowTestCase):

    def test_auth_enforcement(self):
        """Verify endpoints reject requests without API token."""
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        # Missing auth header
        res = self.client.get(f"/api/context-switches?date={today_date}")
        self.assertEqual(res.status_code, 401)
        
        res = self.client.get(f"/api/sessions/history?date={today_date}")
        self.assertEqual(res.status_code, 401)
        
        res = self.client.get("/api/focus/stats?days=7")
        self.assertEqual(res.status_code, 401)

    def test_get_context_switches_happy_and_empty(self):
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        # 1. Empty state
        res = self.client.get(f"/api/context-switches?date={today_date}", headers=self.valid_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["switches"]), 0)
        
        # 2. Insert multiple switches
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.db.write_transaction() as conn:
            conn.execute(
                "INSERT INTO context_switches (timestamp, from_process, to_process) VALUES (?, ?, ?)",
                (now_str, "Code.exe", "chrome.exe")
            )
            conn.execute(
                "INSERT INTO context_switches (timestamp, from_process, to_process) VALUES (?, ?, ?)",
                (now_str, "chrome.exe", "slack.exe")
            )
        
        # 3. Happy path with records
        res = self.client.get(f"/api/context-switches?date={today_date}&limit=50", headers=self.valid_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["switches"]), 2)
        self.assertEqual(data["switches"][0]["from_process"], "Code.exe")

    def test_get_session_history_happy_and_empty(self):
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        # 1. Empty state
        res = self.client.get(f"/api/sessions/history?date={today_date}", headers=self.valid_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["sessions"]), 0)
        
        # 2. Insert sessions
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.db.write_transaction() as conn:
            conn.execute(
                "INSERT INTO sessions (mode, start, end, duration, brain_dump, bypassed, is_flow, flow_duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("work", now_str, now_str, 1800.0, "Focus sprint", 0, 1, 1200.0)
            )
            conn.execute(
                "INSERT INTO sessions (mode, start, end, duration, brain_dump, bypassed, is_flow, flow_duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("recharge", now_str, now_str, 600.0, "Break walk", 0, 0, 0.0)
            )
        
        # 3. Query history
        res = self.client.get(f"/api/sessions/history?date={today_date}", headers=self.valid_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["sessions"]), 2)
        self.assertTrue(data["sessions"][0]["is_flow"])
        self.assertEqual(data["sessions"][0]["flow_duration"], 1200.0)


if __name__ == "__main__":
    unittest.main()
