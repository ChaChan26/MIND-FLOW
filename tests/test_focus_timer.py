"""
Unit tests for focus session timer logging, metrics, and API endpoints.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import unittest
import json
from tests.test_base import BaseMindFlowTestCase
from backend.server import SHARED_API_TOKEN

class TestFocusTimerBackend(BaseMindFlowTestCase):
    def test_db_log_and_stats(self):
        # Test logging a completed session
        res = self.db.log_focus_session(duration_minutes=25, task_label="Coding Feature", completed=1, stamina_start=100.0, stamina_end=85.0)
        self.assertTrue(res)
        
        # Test logging an incomplete session
        self.db.log_focus_session(duration_minutes=15, task_label="Interrupted Task", completed=0, stamina_start=85.0, stamina_end=70.0)
        
        stats = self.db.get_focus_session_stats(days=7)
        self.assertEqual(stats["total_sessions"], 2)
        self.assertEqual(stats["completed_sessions"], 1)
        self.assertEqual(stats["total_focus_minutes"], 25)
        self.assertEqual(stats["avg_duration"], 25.0)

    def test_api_endpoints_auth_enforced(self):
        # Unauthenticated request must be rejected with 401
        res = self.client.get("/api/focus/stats?days=7")
        self.assertEqual(res.status_code, 401)

    def test_api_endpoints_happy_path(self):
        headers = self.get_auth_headers()
        payload = {
            "duration_minutes": 45,
            "task_label": "API Test Focus",
            "completed": 1,
            "stamina_start": 90.0,
            "stamina_end": 75.0
        }
        res = self.client.post("/api/focus/log", data=json.dumps(payload), headers=headers)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data.get("status"), "success")

        stats_res = self.client.get("/api/focus/stats?days=7", headers=headers)
        self.assertEqual(stats_res.status_code, 200)
        stats_data = json.loads(stats_res.data)
        self.assertEqual(stats_data.get("status"), "success")
        self.assertIn("stats", stats_data)

if __name__ == "__main__":
    unittest.main()
