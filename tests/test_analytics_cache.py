"""
Test suite for MIND-FLOW Cognitive Productivity Tracker.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import unittest
import os
import json
from datetime import datetime

os.environ["MINDFLOW_DB_FILE"] = ":memory:"
import backend.database
backend.database.DB_FILE = ":memory:"
from backend.database import MindFlowDB

class TestAnalyticsCache(unittest.TestCase):
    def setUp(self):
        self.db = MindFlowDB()
        self.db._init_db()

    def tearDown(self):
        self.db.close()

    def test_analytics_write_counter_increments(self):
        initial_counter = self.db.analytics_write_counter
        
        # 1. Test add_reflection increments the counter
        res = self.db.add_reflection(energy_level=3, friction_level=2, summary="Test")
        if hasattr(res, 'result'):
            res.result()
            
        self.assertEqual(self.db.analytics_write_counter, initial_counter + 1)
        initial_counter += 1
        
        # 2. Test log_session increments the counter
        from datetime import timedelta
        res = self.db.log_session(mode="work", start_time=datetime.now() - timedelta(minutes=10), end_time=datetime.now())
        if hasattr(res, 'result'):
            res.result()
        self.assertEqual(self.db.analytics_write_counter, initial_counter + 1)
        initial_counter += 1
        
        # 3. Test update_settings increments the counter
        res = self.db.update_settings({"work_duration_minutes": 50})
        if hasattr(res, 'result'):
            res.result()
        self.assertEqual(self.db.analytics_write_counter, initial_counter + 1)
        initial_counter += 1

    def test_clear_analytics_cache_invokes(self):
        from backend.server import _analytics_cache, _analytics_cache_lock
        with _analytics_cache_lock:
            _analytics_cache["dummy_key"] = {"test": 123}

        self.db.clear_analytics_cache()

        with _analytics_cache_lock:
            self.assertNotIn("dummy_key", _analytics_cache)

if __name__ == '__main__':
    unittest.main()
