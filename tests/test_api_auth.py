"""
Unit tests for API Authentication and route safety invariants.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseMindFlowTestCase
from backend.server import SHARED_API_TOKEN, shared_state

class TestAPIAuthAndRouteSafety(BaseMindFlowTestCase):
    def test_unauthorized_access_without_token(self):
        """Verify API endpoints return 401 Unauthorized when token is missing or invalid."""
        # 1. Missing token
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertIn("error", data)

        # 2. Invalid token
        resp_invalid = self.client.get("/api/status", headers={"X-MIND-FLOW-TOKEN": "invalid_secret_token"})
        self.assertEqual(resp_invalid.status_code, 401)

    def test_authorized_access_via_token_header_and_bearer_and_cookie(self):
        """Verify token authentication succeeds via X-MIND-FLOW-TOKEN, Bearer auth, and cookie."""
        # 1. Header X-MIND-FLOW-TOKEN
        resp1 = self.client.get("/api/status", headers=self.get_auth_headers())
        self.assertEqual(resp1.status_code, 200)

        # 2. Authorization Bearer header
        resp2 = self.client.get("/api/status", headers={"Authorization": f"Bearer {SHARED_API_TOKEN}", "Host": "127.0.0.1:5000", "Origin": "http://127.0.0.1:5000"})
        self.assertEqual(resp2.status_code, 200)

        # 3. Cookie MIND_FLOW_TOKEN
        self.client.set_cookie("MIND_FLOW_TOKEN", SHARED_API_TOKEN, domain="localhost")
        resp3 = self.client.get("/api/status", headers={"Host": "localhost:5000", "Origin": "http://localhost:5000"})
        self.assertEqual(resp3.status_code, 200)

    def test_host_header_dns_rebinding_protection(self):
        """Verify Host header validation blocks foreign domains (DNS Rebinding protection)."""
        # Valid host
        resp_valid = self.client.get("/api/status", headers={"X-MIND-FLOW-TOKEN": SHARED_API_TOKEN, "Host": "127.0.0.1:5000", "Origin": "http://127.0.0.1:5000"})
        self.assertEqual(resp_valid.status_code, 200)

        # Invalid attacker host
        resp_blocked = self.client.get("/api/status", headers={"X-MIND-FLOW-TOKEN": SHARED_API_TOKEN, "Host": "attacker-domain.com"})
        self.assertEqual(resp_blocked.status_code, 403)
        self.assertIn("Invalid Host", resp_blocked.get_json()["error"])

    def test_origin_header_csrf_protection(self):
        """Verify Origin header validation blocks untrusted origins."""
        # Valid origin
        resp_valid = self.client.post("/api/set_mode", headers={"X-MIND-FLOW-TOKEN": SHARED_API_TOKEN, "Origin": "http://localhost:5000", "Content-Type": "application/json", "Host": "127.0.0.1:5000"}, json={"mode": "work"})
        self.assertEqual(resp_valid.status_code, 200)

        # Blocked origin
        resp_blocked = self.client.post("/api/set_mode", headers={"X-MIND-FLOW-TOKEN": SHARED_API_TOKEN, "Origin": "http://evil-site.com", "Content-Type": "application/json", "Host": "127.0.0.1:5000"}, json={"mode": "work"})
        self.assertEqual(resp_blocked.status_code, 403)
        self.assertIn("invalid origin", resp_blocked.get_json()["error"].lower())

    def test_settings_payload_input_validation_clamping(self):
        """Verify POST /api/settings safely clamps out-of-bounds numeric inputs."""
        payload = {
            "work_duration_minutes": 999999,  # Should clamp to 180
            "rest_duration_seconds": -50,     # Should clamp to 10
            "daily_sleep_target": 100         # Should clamp to 24
        }
        resp = self.client.post(
            "/api/settings",
            headers=self.get_auth_headers(),
            json=payload
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        settings = data.get("settings", data)
        self.assertEqual(settings["work_duration_minutes"], 180)
        self.assertEqual(settings["rest_duration_seconds"], 5)
        self.assertEqual(settings["daily_sleep_target"], 24)

if __name__ == "__main__":
    unittest.main()
