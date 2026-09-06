"""
Unit tests for Achievements API endpoint and unlock verification.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_base import BaseMindFlowTestCase


class TestAchievements(BaseMindFlowTestCase):

    def test_achievements_auth_enforcement(self):
        """Verify GET /api/achievements requires authentication."""
        res = self.client.get("/api/achievements")
        self.assertEqual(res.status_code, 401)

    def test_achievements_retrieval(self):
        """Verify GET /api/achievements returns the list of system achievements."""
        res = self.client.get("/api/achievements", headers=self.valid_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
