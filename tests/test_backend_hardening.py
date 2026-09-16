"""
Unit tests for backend hardening: DuckDB teardown, WAL passive checkpoint, CRDT GC, ReDoS safety.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import unittest
import time
import tempfile
import shutil

# Ensure c:\MIND is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import MindFlowDB, is_safe_regex
from backend.columnar_analytics import ColumnarAnalyticsEngine
from backend.task_classifier import TaskClassifier
from backend.crdt_sync import CRDTSyncEngine, HLCTimestamp


class TestBackendHardening(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_mind_flow.db")
        self.duck_path = os.path.join(self.temp_dir, "test_analytics.duckdb")
        self.db = MindFlowDB(db_path=self.db_path)

    def tearDown(self):
        if hasattr(self, 'db') and self.db:
            try:
                self.db.flush_queue()
                self.db.close()
            except Exception:
                pass
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_duckdb_clean_teardown(self):
        """Verify ColumnarAnalyticsEngine closes DuckDB connections cleanly."""
        engine = ColumnarAnalyticsEngine(db_path=self.duck_path, sqlite_db=self.db, batch_size=10, flush_interval=0.5)
        engine.append_window_log(time.time(), "code.exe", "test.py - VS Code", "work", 2.5)
        time.sleep(0.7)  # Allow batch worker to flush
        engine.close()
        self.assertIsNone(engine._duck_conn)

    def test_wal_checkpoint_and_flush(self):
        """Verify flush_app_usage triggers passive WAL checkpoint without error."""
        with self.db.buffer_lock:
            self.db.app_usage_buffer[("chrome.exe", "Stack Overflow")] = 5.0
        self.db.flush_app_usage()
        # Verify app_usage record was persisted
        usage = self.db.get_app_usage()
        self.assertTrue(any(u["process"] == "chrome.exe" for u in usage))

    def test_task_classifier_cache_invalidation(self):
        """Verify TaskClassifier clear_cache empties the Tier 1 LRU cache."""
        classifier = TaskClassifier()
        cat1 = classifier.classify("code.exe", "main.py - VS Code")
        self.assertEqual(cat1, "work")
        stats_before = classifier.get_stats()
        self.assertGreaterEqual(stats_before["lru_cache_size"], 1)

        classifier.clear_cache()
        stats_after = classifier.get_stats()
        self.assertEqual(stats_after["lru_cache_size"], 0)

    def test_crdt_tombstone_gc_and_delta(self):
        """Verify CRDTSyncEngine tombstone garbage collection and delta export."""
        engine = CRDTSyncEngine(node_id="node_test_1")
        engine.add_category_rule("rule_1", timestamp=HLCTimestamp(time.time() - 100000.0, 0, "node_test_1"))
        engine.remove_category_rule("rule_1", timestamp=HLCTimestamp(time.time() - 90000.0, 1, "node_test_1"))

        purged_count = engine.garbage_collect_tombstones(max_age_seconds=86400.0)
        self.assertEqual(purged_count, 1)

        # Verify delta export
        engine.add_category_rule("rule_2")
        delta = engine.export_delta(since_physical_time=time.time() - 10.0)
        self.assertIn("category_rules", delta)

    def test_redos_safety_validation(self):
        """Verify is_safe_regex correctly catches catastrophic backtracking patterns."""
        self.assertTrue(is_safe_regex(r"^[\w\.-]+@[\w\.-]+\.\w+$"))
        self.assertFalse(is_safe_regex(r"(a+)+b"))


if __name__ == "__main__":
    unittest.main()
