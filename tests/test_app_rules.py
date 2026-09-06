"""
Unit tests for application classification rule database and API endpoints.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import json
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_base import BaseMindFlowTestCase


class TestAppRules(BaseMindFlowTestCase):

    def test_app_rules_db_crud(self):
        """Test database layer CRUD operations."""
        # 1. Test get_app_rules initially
        rules = self.db.get_app_rules()
        self.assertIsInstance(rules, list)
        
        # 2. Add custom app rule
        self.db.recategorize_app("godot.exe", "work")
        rules = self.db.get_app_rules()
        godot_rule = next((r for r in rules if r["app_name"] == "godot.exe"), None)
        self.assertIsNotNone(godot_rule)
        self.assertEqual(godot_rule["category"], "work")

        # 3. Recategorize to recharge
        self.db.recategorize_app("godot.exe", "recharge")
        rules = self.db.get_app_rules()
        godot_rule = next((r for r in rules if r["app_name"] == "godot.exe"), None)
        self.assertIsNotNone(godot_rule)
        self.assertEqual(godot_rule["category"], "recharge")

        # 4. Delete rule
        self.db.delete_app_rule("godot.exe")
        rules = self.db.get_app_rules()
        godot_rule = next((r for r in rules if r["app_name"] == "godot.exe"), None)
        self.assertIsNone(godot_rule)

    def test_app_rules_api_endpoints(self):
        """Test HTTP API layer for /api/app_rules and recategorization."""
        # GET /api/app_rules
        resp = self.client.get("/api/app_rules", headers=self.get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "success")
        self.assertIn("rules", data)
        self.assertIn("work_keywords", data)

        # POST /api/app_rules
        post_resp = self.client.post(
            "/api/app_rules",
            headers=self.get_auth_headers(),
            data=json.dumps({"app_name": "blender.exe", "category": "work"})
        )
        self.assertEqual(post_resp.status_code, 200)
        rules = post_resp.get_json().get("rules", [])
        self.assertTrue(any(r["app_name"] == "blender.exe" and r["category"] == "work" for r in rules))

        # POST /api/app_rules/recategorize
        re_resp = self.client.post(
            "/api/app_rules/recategorize",
            headers=self.get_auth_headers(),
            data=json.dumps({"app_name": "blender.exe", "category": "neutral"})
        )
        self.assertEqual(re_resp.status_code, 200)
        rules = re_resp.get_json().get("rules", [])
        self.assertTrue(any(r["app_name"] == "blender.exe" and r["category"] == "neutral" for r in rules))

        # DELETE /api/app_rules
        del_resp = self.client.delete(
            "/api/app_rules?app_name=blender.exe",
            headers=self.get_auth_headers()
        )
        self.assertEqual(del_resp.status_code, 200)
        rules = del_resp.get_json().get("rules", [])
        self.assertFalse(any(r["app_name"] == "blender.exe" for r in rules))

    def test_app_rules_api_validation_and_auth(self):
        """Test validation failure and auth rejection on app rules endpoints."""
        # Missing app_name
        resp = self.client.post(
            "/api/app_rules",
            headers=self.get_auth_headers(),
            data=json.dumps({"category": "work"})
        )
        self.assertEqual(resp.status_code, 400)

        # Unauthenticated request
        unauth = self.client.get("/api/app_rules")
        self.assertEqual(unauth.status_code, 401)


if __name__ == "__main__":
    unittest.main()
