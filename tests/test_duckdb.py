"""
Test suite for MIND-FLOW Cognitive Productivity Tracker.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import time
import unittest
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch

# Set memory database env var BEFORE importing backend modules
os.environ["MINDFLOW_DB_FILE"] = ":memory:"
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import MindFlowDB
from backend.columnar_analytics import ColumnarAnalyticsEngine


class TestColumnarAnalyticsEngine(unittest.TestCase):
    def setUp(self):
        self.db = MindFlowDB()
        self.engine = ColumnarAnalyticsEngine(db_path=":memory:", sqlite_db=self.db)

    def tearDown(self):
        self.engine.close()
        self.db.close()

    def test_duckdb_queue_batch_append(self):
        now = time.time()
        # Append window logs to async batch queue
        self.engine.append_window_log(now - 100, "Code.exe", "index.py - MIND", "work", 300.0)
        self.engine.append_window_log(now - 50, "spotify.exe", "Spotify Premium", "recharge", 120.0)
        self.engine.append_window_log(now, "chrome.exe", "Google Search", "neutral", 60.0)

        # Flush queue to DuckDB
        self.engine.flush()

        # Query DuckDB directly to verify columnar table ingestion
        conn = self.engine._get_connection(read_only=False)
        rows = conn.execute("SELECT COUNT(*), SUM(duration) FROM active_window_logs").fetchone()
        self.assertEqual(rows[0], 3)
        self.assertEqual(rows[1], 480.0)

    def test_daily_productivity_trends(self):
        now = time.time()
        # Add logs across different days
        self.engine.append_window_log(now - 86400 * 2, "Code.exe", "VS Code", "work", 3600.0)
        self.engine.append_window_log(now - 86400 * 2, "vlc.exe", "VLC", "recharge", 1800.0)
        self.engine.append_window_log(now - 86400 * 1, "Code.exe", "VS Code", "work", 7200.0)
        self.engine.flush()

        trends = self.engine.get_daily_productivity_trends(days=3)
        self.assertIsInstance(trends, list)
        self.assertGreaterEqual(len(trends), 3)

        # Check keys in trend dict
        for item in trends:
            self.assertIn("date", item)
            self.assertIn("work_seconds", item)
            self.assertIn("rest_seconds", item)
            self.assertIn("neutral_seconds", item)
            self.assertIn("total_seconds", item)
            self.assertIn("productivity_score", item)

    def test_category_breakdown(self):
        start_ts = time.time() - 3600
        end_ts = time.time() + 100

        self.engine.append_window_log(start_ts + 10, "Code.exe", "VS Code", "work", 1200.0)
        self.engine.append_window_log(start_ts + 20, "Discord.exe", "Discord Chat", "recharge", 400.0)
        self.engine.append_window_log(start_ts + 30, "Explorer.exe", "File Explorer", "neutral", 200.0)
        self.engine.flush()

        breakdown = self.engine.get_category_breakdown(start_ts, end_ts)
        self.assertIsInstance(breakdown, dict)
        self.assertEqual(breakdown.get("work"), 1200.0)
        self.assertEqual(breakdown.get("recharge"), 400.0)
        self.assertEqual(breakdown.get("neutral"), 200.0)

    def test_fatigue_duration_analytics(self):
        now = time.time()
        # Add continuous work blocks (>45 mins)
        self.engine.append_window_log(now - 5000, "Code.exe", "VS Code", "work", 3000.0)
        self.engine.append_window_log(now - 1000, "vlc.exe", "VLC", "recharge", 600.0)
        self.engine.flush()

        fatigue = self.engine.get_fatigue_duration_analytics(days=7)
        self.assertIsInstance(fatigue, dict)
        self.assertIn("total_work_seconds", fatigue)
        self.assertIn("total_rest_seconds", fatigue)
        self.assertIn("avg_daily_work_seconds", fatigue)
        self.assertIn("longest_continuous_work_seconds", fatigue)
        self.assertIn("fatigue_risk_score", fatigue)
        self.assertIn("hourly_distribution", fatigue)
        self.assertEqual(len(fatigue["hourly_distribution"]), 24)

    def test_sqlite_failover(self):
        now = time.time()
        # Log usage to SQLite
        self.db.log_app_usage("code.exe", "VS Code", 1800.0)
        self.db.flush_app_usage()

        # Simulate DuckDB exception to force failover
        with patch.object(self.engine, '_get_daily_productivity_trends_duckdb', side_effect=Exception("DuckDB Lock Error")):
            trends = self.engine.get_daily_productivity_trends(days=3)
            self.assertIsInstance(trends, list)
            self.assertGreaterEqual(len(trends), 3)

        with patch.object(self.engine, '_get_category_breakdown_duckdb', side_effect=Exception("DuckDB Lock Error")):
            breakdown = self.engine.get_category_breakdown(now - 86400, now + 86400)
            self.assertIsInstance(breakdown, dict)

        with patch.object(self.engine, '_get_fatigue_duration_analytics_duckdb', side_effect=Exception("DuckDB Lock Error")):
            fatigue = self.engine.get_fatigue_duration_analytics(days=7)
            self.assertIsInstance(fatigue, dict)

    def test_database_analytics_routing(self):
        # Test routing methods directly on MindFlowDB
        self.db.log_app_usage("pycharm.exe", "Project.py", 600.0)
        self.db.flush_queue()

        trends = self.db.get_daily_productivity_trends(days=7)
        self.assertIsInstance(trends, list)

        breakdown = self.db.get_category_breakdown()
        self.assertIsInstance(breakdown, dict)

        fatigue = self.db.get_fatigue_duration_analytics(days=30)
        self.assertIsInstance(fatigue, dict)


if __name__ == "__main__":
    unittest.main()
