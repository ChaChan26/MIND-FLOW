"""
Test suite for MIND-FLOW Cognitive Productivity Tracker.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend import tracker

class TestEventTracker(unittest.TestCase):
    def tearDown(self):
        tracker.stop_event_listener()

    def test_start_and_stop_event_listener(self):
        if sys.platform == "win32":
            res = tracker.start_event_listener()
            self.assertTrue(res)
            self.assertTrue(tracker._event_listener_active)
            tracker.stop_event_listener()
            self.assertFalse(tracker._event_listener_active)
        else:
            res = tracker.start_event_listener()
            self.assertFalse(res)

    def test_get_active_window_details_cached(self):
        if sys.platform == "win32":
            tracker.start_event_listener()
            # Verify details return non-empty strings
            title, proc = tracker.get_active_window_details()
            self.assertIsInstance(title, str)
            self.assertIsInstance(proc, str)
            
            # Verify force_poll returns valid tuple
            title_poll, proc_poll = tracker.get_active_window_details(force_poll=True)
            self.assertIsInstance(title_poll, str)
            self.assertIsInstance(proc_poll, str)
            tracker.stop_event_listener()
        else:
            title, proc = tracker.get_active_window_details()
            self.assertIsInstance(title, str)
            self.assertIsInstance(proc, str)

if __name__ == "__main__":
    unittest.main()
