"""
Unit tests for core Flask API endpoints and mode transition safety.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseMindFlowTestCase
from backend.server import SHARED_API_TOKEN, shared_state, app

class TestAPIEndpoints(BaseMindFlowTestCase):
    def setUp(self):
        super().setUp()
        # Reset shared state defaults
        shared_state["current_mode"] = "neutral"
        shared_state["elapsed_seconds"] = 0
        shared_state["idle_seconds"] = 0
        shared_state["tracking_active"] = True

    def test_set_mode_success(self):
        """Verify POST /api/set_mode switches valid modes cleanly."""
        modes_to_test = ["work", "recharge", "rest", "neutral"]
        for mode in modes_to_test:
            with self.subTest(mode=mode):
                resp = self.client.post(
                    "/api/set_mode",
                    headers=self.valid_headers,
                    json={"mode": mode}
                )
                self.assertEqual(resp.status_code, 200)
                data = resp.get_json()
                self.assertEqual(data.get("status"), "success")
                self.assertEqual(data.get("current_mode"), mode)
                self.assertEqual(shared_state["current_mode"], mode)
                self.assertEqual(shared_state["elapsed_seconds"], 0)

    def test_set_mode_invalid_or_missing_payload(self):
        """Verify POST /api/set_mode returns 400 for missing or invalid modes."""
        invalid_payloads = [
            {},
            {"mode": "superman"},
            {"mode": 123},
            {"mode": None},
            {"invalid_key": "work"}
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                resp = self.client.post(
                    "/api/set_mode",
                    headers=self.valid_headers,
                    json=payload
                )
                self.assertEqual(resp.status_code, 400)
                data = resp.get_json()
                self.assertIn("error", data)

    def test_set_mode_unauthorized(self):
        """Verify POST /api/set_mode blocks unauthorized requests with 401."""
        # 1. Missing token
        resp1 = self.client.post("/api/set_mode", json={"mode": "work"})
        self.assertEqual(resp1.status_code, 401)

        # 2. Invalid token
        resp2 = self.client.post(
            "/api/set_mode",
            headers={"X-MIND-FLOW-TOKEN": "wrong_token", "Origin": "http://127.0.0.1:5000"},
            json={"mode": "work"}
        )
        self.assertEqual(resp2.status_code, 401)

    def test_status_double_counting_protection(self):
        """Verify GET /api/status does not double-count elapsed session seconds across multiple calls or mode switches."""
        # Clear sessions in database for clean baseline
        with self.db.connection() as conn:
            conn.execute("DELETE FROM sessions")

        shared_state["current_mode"] = "work"
        shared_state["elapsed_seconds"] = 120

        # Initial status query
        resp1 = self.client.get("/api/status", headers=self.valid_headers)
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.get_json()
        work_sec_1 = data1.get("today_work_seconds")
        self.assertEqual(work_sec_1, 120)

        # Second status query without state change should yield identical total (no double counting)
        resp2 = self.client.get("/api/status", headers=self.valid_headers)
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()
        self.assertEqual(data2.get("today_work_seconds"), 120)

        # Transition mode to neutral via set_mode endpoint
        resp_mode = self.client.post("/api/set_mode", headers=self.valid_headers, json={"mode": "neutral"})
        self.assertEqual(resp_mode.status_code, 200)

        # Query status again; neutral mode with 0 elapsed should not double-count or report stale work seconds
        resp3 = self.client.get("/api/status", headers=self.valid_headers)
        self.assertEqual(resp3.status_code, 200)
        data3 = resp3.get_json()
        self.assertEqual(data3.get("today_work_seconds"), 0)

    def test_x_mind_flow_token_header_auth(self):
        """Verify API auth works with X-MIND-FLOW-TOKEN, Bearer header, and Cookie, while rejecting missing/invalid tokens."""
        endpoints = [
            ("/api/status", "GET", None),
            ("/api/settings", "GET", None),
            ("/api/hydration", "GET", None),
            ("/api/workspace/status", "GET", None)
        ]

        for url, method, body in endpoints:
            with self.subTest(url=url):
                # Clean client per test to prevent cookie bleed
                test_client = app.test_client()

                # Missing token -> 401
                r_missing = test_client.open(url, method=method, json=body)
                self.assertEqual(r_missing.status_code, 401)

                # Invalid token -> 401
                r_invalid = test_client.open(url, method=method, headers={"X-MIND-FLOW-TOKEN": "bad_token"}, json=body)
                self.assertEqual(r_invalid.status_code, 401)

                # Valid X-MIND-FLOW-TOKEN header -> 200
                r_valid = test_client.open(url, method=method, headers=self.get_auth_headers(), json=body)
                self.assertEqual(r_valid.status_code, 200)

                # Valid Authorization Bearer header -> 200
                r_bearer = test_client.open(url, method=method, headers={"Authorization": f"Bearer {SHARED_API_TOKEN}", "Host": "127.0.0.1:5000", "Origin": "http://127.0.0.1:5000"}, json=body)
                self.assertEqual(r_bearer.status_code, 200)

                # Valid Cookie -> 200
                test_client.set_cookie("MIND_FLOW_TOKEN", SHARED_API_TOKEN, domain="localhost")
                r_cookie = test_client.open(url, method=method, headers={"Host": "localhost:5000", "Origin": "http://localhost:5000"}, json=body)
                self.assertEqual(r_cookie.status_code, 200)

    def test_get_running_apps_endpoint(self):
        """Verify GET /api/app_rules/running returns 200 and running_apps array."""
        resp = self.client.get("/api/app_rules/running", headers=self.valid_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("running_apps", data)
        self.assertIsInstance(data["running_apps"], list)

if __name__ == "__main__":
    unittest.main()
