"""
Test suite for MIND-FLOW Cognitive Productivity Tracker.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import unittest

os.environ["MINDFLOW_DB_FILE"] = ":memory:"
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import unittest
import sys
import time
from unittest.mock import patch, MagicMock

# Import from our newly refactored module
from backend.tracker import (
    get_active_window_details,
    get_idle_seconds,
    is_passive_viewing_active
)

class TestTracker(unittest.TestCase):
    def test_get_idle_seconds_type(self):
        # get_idle_seconds should return a float or int >= 0
        idle = get_idle_seconds()
        self.assertTrue(isinstance(idle, (int, float)))
        self.assertGreaterEqual(idle, 0)
        
    def test_get_active_window_details(self):
        # We don't want to enforce specific values since it runs in a real environment
        # but we can ensure it returns a tuple of (title, process) strings
        title, process = get_active_window_details()
        self.assertTrue(isinstance(title, str))
        self.assertTrue(isinstance(process, str))
        
    @patch('backend.tracker.is_audio_playing')
    def test_is_passive_viewing_active(self, mock_audio):
        # Mock audio to be playing
        mock_audio.return_value = True
        
        # Test with a media app
        self.assertTrue(is_passive_viewing_active("vlc.exe", "movie"))
        
        # Test with a browser viewing a video
        self.assertTrue(is_passive_viewing_active("chrome.exe", "youtube - cool video"))
        
        # Test with a browser not viewing a video
        self.assertFalse(is_passive_viewing_active("chrome.exe", "some random site"))
        
        # Mock audio to be false
        mock_audio.return_value = False
        
        # Test with media app but no audio
        self.assertFalse(is_passive_viewing_active("vlc.exe", "movie"))

    @patch('backend.tracker.check_windows_audio_active')
    def test_is_audio_playing_cooldown_fast_path(self, mock_win_audio):
        """Verify R3: Fast-path skips expensive audio checks within 5s cooldown."""
        import backend.tracker as tracker_module
        now = time.time()
        with tracker_module._audio_time_lock:
            tracker_module._last_audio_active_time = now
            tracker_module._last_audio_check_time = now
            tracker_module._last_audio_result = True
        
        mock_win_audio.return_value = True
        mock_win_audio.reset_mock()
        
        # Within 5s cooldown fast-path, is_audio_playing() returns True immediately without OS check
        self.assertTrue(tracker_module.is_audio_playing())
        self.assertEqual(mock_win_audio.call_count, 0)

        # Force expire cooldown (> 5s ago)
        with tracker_module._audio_time_lock:
            tracker_module._last_audio_active_time = time.time() - 10.0
            tracker_module._last_audio_check_time = time.time() - 10.0
            tracker_module._last_audio_result = False
            
        mock_win_audio.return_value = False
        self.assertFalse(tracker_module.is_audio_playing())
        self.assertEqual(mock_win_audio.call_count, 1)

if __name__ == '__main__':
    unittest.main()
