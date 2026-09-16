"""
Test suite for MIND-FLOW Cognitive Productivity Tracker.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import time
import unittest
import threading
import queue
from datetime import datetime, timedelta

# Set memory database env var BEFORE importing backend modules to ensure isolation
os.environ["MINDFLOW_DB_FILE"] = ":memory:"

# Add backend to path so we can import database & tracker
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import MindFlowDB, matches_any_keyword, clear_regex_caches
from backend.server import StandardDictWrapper
from backend import tracker


class TestStandardDictWrapper(unittest.TestCase):
    def test_standard_dict_wrapper_concurrency(self):
        wrapper = StandardDictWrapper({"key": 0, "pop_key": 100})
        stop_event = threading.Event()
        errors = []

        def writer():
            try:
                for count in range(100):
                    if stop_event.is_set():
                        break
                    wrapper["key"] = count
                    wrapper[f"key_{count % 10}"] = count
                    wrapper.setdefault(f"def_{count % 5}", count)
                    if "pop_key" in wrapper:
                        _ = wrapper.pop("pop_key", None)
                    else:
                        wrapper["pop_key"] = count
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(100):
                    if stop_event.is_set():
                        break
                    snapshot = wrapper.get_snapshot()
                    self.assertIsInstance(snapshot, dict)
                    _ = wrapper.get("key")
                    _ = wrapper.keys()
                    _ = wrapper.values()
                    _ = wrapper.items()
                    _ = len(wrapper)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader)
        ]
        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=2.0)
            self.assertFalse(t.is_alive(), "Worker thread hung in StandardDictWrapper test")

        stop_event.set()
        self.assertEqual(len(errors), 0, f"Errors in concurrent StandardDictWrapper test: {errors}")


class TestRegexCacheLocking(unittest.TestCase):
    def test_regex_cache_locking(self):
        keywords = ["vs code", "python", "pytest", "github"]
        stop_event = threading.Event()
        errors = []

        def matcher():
            try:
                for _ in range(100):
                    if stop_event.is_set():
                        break
                    matches_any_keyword(keywords, "working in vs code on python")
            except Exception as e:
                errors.append(e)

        def clearer():
            try:
                for _ in range(50):
                    if stop_event.is_set():
                        break
                    clear_regex_caches()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=matcher),
            threading.Thread(target=clearer)
        ]
        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=2.0)
            self.assertFalse(t.is_alive(), "Worker thread hung in RegexCacheLocking test")

        stop_event.set()
        self.assertEqual(len(errors), 0, f"Errors in concurrent RegexCacheLocking test: {errors}")


class TestMindFlowDatabaseR1(unittest.TestCase):
    def setUp(self):
        import backend.database
        os.environ["MINDFLOW_DB_FILE"] = ":memory:"
        backend.database.DB_FILE = ":memory:"
        with MindFlowDB._settings_lock:
            MindFlowDB._settings_cache = None
        self.db = MindFlowDB()

    def tearDown(self):
        import backend.database
        backend.database.DB_FILE = ":memory:"
        self.db.close()
        with MindFlowDB._settings_lock:
            MindFlowDB._settings_cache = None

    def test_db_lifecycle_and_queued_write(self):
        self.assertTrue(hasattr(self.db, "_write_queue"))
        now = datetime.now()
        self.db.log_session("work", now - timedelta(minutes=1), now, is_flow=True, flow_duration=60.0, wait=True)
        
        future = self.db.log_session("recharge", now - timedelta(minutes=2), now - timedelta(minutes=1), wait=False)
        self.assertIsNotNone(future)
        if hasattr(future, 'result'):
            future.result()

    def test_settings_deepcopy_and_invalidation(self):
        settings_1 = self.db.get_settings()
        self.assertIsInstance(settings_1, dict)
        
        # Modify returned dict in place
        settings_1["work_duration_minutes"] = 9999
        
        # Subsequent call should return original cached settings, NOT mutated in-place value
        settings_2 = self.db.get_settings()
        self.assertNotEqual(settings_2.get("work_duration_minutes"), 9999)
        
        # Updating settings should invalidate cache and persist new value
        res = self.db.update_settings({"work_duration_minutes": 45})
        if hasattr(res, 'result'):
            res.result()
        settings_3 = self.db.get_settings()
        self.assertEqual(settings_3.get("work_duration_minutes"), 45)

    def test_composite_indexes_exist(self):
        with self.db.connection() as conn:
            session_indexes = [row["name"] for row in conn.execute("PRAGMA index_list('sessions')").fetchall()]
            cs_indexes = [row["name"] for row in conn.execute("PRAGMA index_list('context_switches')").fetchall()]
            
            self.assertIn("idx_sessions_mode_start", session_indexes)
            self.assertIn("idx_context_switches_ts", cs_indexes)

    def test_queued_write_retry_logic(self):
        import sqlite3
        from backend.database import queued_write
        
        attempts = 0
        
        class DummyDB(MindFlowDB):
            @queued_write
            def flaky_write(self):
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise sqlite3.OperationalError("database is locked")
                return "success"
                
        dummy = DummyDB()
        try:
            res = dummy.flaky_write(wait=True)
            self.assertEqual(res, "success")
            self.assertEqual(attempts, 3)
        finally:
            dummy.close()

    def test_queued_write_retry_exhaustion(self):
        import sqlite3
        from backend.database import queued_write
        
        attempts = 0
        
        class DummyDB(MindFlowDB):
            @queued_write
            def failing_write(self):
                nonlocal attempts
                attempts += 1
                raise sqlite3.OperationalError("database is locked")
                
        dummy = DummyDB()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                dummy.failing_write(wait=True)
            self.assertEqual(attempts, 4)
        finally:
            dummy.close()

    def test_queued_write_fast_failure(self):
        import sqlite3
        from backend.database import queued_write
        
        attempts = 0
        
        class DummyDB(MindFlowDB):
            @queued_write
            def integrity_failing_write(self):
                nonlocal attempts
                attempts += 1
                raise sqlite3.IntegrityError("UNIQUE constraint failed: test.id")
                
        dummy = DummyDB()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                dummy.integrity_failing_write(wait=True)
            self.assertEqual(attempts, 1)
        finally:
            dummy.close()

    def test_write_queue_maxsize_bound(self):
        db = MindFlowDB()
        try:
            self.assertEqual(db._write_queue.maxsize, 1000)
            # Verify queue.Full handling on wait=False without NameError
            db._write_queue = queue.Queue(maxsize=1)
            db.save(wait=False)  # 1 item queued
            fut = db.save(wait=False)  # Queue full -> drops and sets exception cleanly
            self.assertIsNotNone(fut.exception())
            self.assertIsInstance(fut.exception(), queue.Full)
        finally:
            db.close()




class TestTrackerProcessHandleCaching(unittest.TestCase):
    def setUp(self):
        with tracker._hwnd_cache_lock:
            tracker._last_hwnd = None
            tracker._cached_process_name = None

    def tearDown(self):
        with tracker._hwnd_cache_lock:
            tracker._last_hwnd = None
            tracker._cached_process_name = None

    def test_zero_and_none_hwnd_handling(self):
        self.assertEqual(tracker.get_active_process_name_direct(0), "None")
        self.assertEqual(tracker.get_active_process_name_direct(None), "None")

    def test_hwnd_cache_hit(self):
        with tracker._hwnd_cache_lock:
            tracker._last_hwnd = 123456
            tracker._cached_process_name = "test_app.exe"
        
        # Calling with same hwnd should return cached process name without OS calls
        res = tracker.get_active_process_name_direct(123456)
        self.assertEqual(res, "test_app.exe")

    def test_hwnd_cache_reset_on_new_hwnd(self):
        with tracker._hwnd_cache_lock:
            tracker._last_hwnd = 123456
            tracker._cached_process_name = "test_app.exe"
        
        # Calling with invalid/zero hwnd should clear cache
        tracker.get_active_process_name_direct(0)
        with tracker._hwnd_cache_lock:
            self.assertIsNone(tracker._last_hwnd)
            self.assertIsNone(tracker._cached_process_name)


if __name__ == "__main__":
    unittest.main()
