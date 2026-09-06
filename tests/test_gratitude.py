"""
Unit tests for Gratitude journaling API endpoints and database operations.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import unittest
import json
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_base import BaseMindFlowTestCase


class TestGratitude(BaseMindFlowTestCase):

    def test_gratitude_auth_enforcement(self):
        """Verify gratitude endpoints require authentication."""
        today_str = date.today().isoformat()
        
        # GET without auth
        res = self.client.get(f"/api/gratitude?date={today_str}")
        self.assertEqual(res.status_code, 401)
        
        # POST without auth
        payload = {"entry_1": "Sunlight", "entry_2": "Coffee", "entry_3": "Focus"}
        res = self.client.post(f"/api/gratitude?date={today_str}", data=json.dumps(payload))
        self.assertEqual(res.status_code, 401)

    def test_gratitude_empty_state(self):
        """Verify GET returns empty template if no entries logged for date."""
        today_str = date.today().isoformat()
        res = self.client.get(f"/api/gratitude?date={today_str}", headers=self.valid_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["entry_1"], "")
        self.assertEqual(data["entry_2"], "")
        self.assertEqual(data["entry_3"], "")

    def test_gratitude_roundtrip(self):
        """Verify logging gratitude and retrieving it for a specific date."""
        today_str = "2026-08-16"
        payload = {
            "entry_1": "Morning run in cool weather",
            "entry_2": "Clean architecture refactor",
            "entry_3": "Good rest"
        }
        post_res = self.client.post(
            f"/api/gratitude?date={today_str}",
            data=json.dumps(payload),
            headers=self.valid_headers
        )
        self.assertEqual(post_res.status_code, 200)
        
        get_res = self.client.get(f"/api/gratitude?date={today_str}", headers=self.valid_headers)
        self.assertEqual(get_res.status_code, 200)
        data = get_res.get_json()
        self.assertEqual(data["entry_1"], "Morning run in cool weather")
        self.assertEqual(data["entry_2"], "Clean architecture refactor")
        self.assertEqual(data["entry_3"], "Good rest")

    def test_gratitude_truncation(self):
        """Verify long entries are safely capped at 1000 characters."""
        today_str = "2026-08-16"
        long_text = "A" * 1500
        payload = {"entry_1": long_text, "entry_2": "Short", "entry_3": "Short"}
        self.client.post(
            f"/api/gratitude?date={today_str}",
            data=json.dumps(payload),
            headers=self.valid_headers
        )
        
        get_res = self.client.get(f"/api/gratitude?date={today_str}", headers=self.valid_headers)
        data = get_res.get_json()
        self.assertEqual(len(data["entry_1"]), 1000)


if __name__ == "__main__":
    unittest.main()
