"""
Unit tests for calendar sync SSRF prevention, iCal parsing, and lock contention.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import unittest
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_base import BaseMindFlowTestCase
from backend.server import is_safe_url


class TestCalendarSync(BaseMindFlowTestCase):

    def test_is_safe_url_ssrf_blocking(self):
        """Verify is_safe_url blocks private IPs, loopback, metadata, and invalid schemes."""
        # Invalid schemes
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url("ftp://127.0.0.1/test"))
        self.assertFalse(is_safe_url("gopher://localhost:70"))
        self.assertFalse(is_safe_url(""))
        self.assertFalse(is_safe_url("not_a_url"))
        
        # Loopback
        self.assertFalse(is_safe_url("http://127.0.0.1/calendar.ics"))
        self.assertFalse(is_safe_url("http://localhost/calendar.ics"))
        self.assertFalse(is_safe_url("http://[::1]/calendar.ics"))
        
        # Link-local & cloud metadata
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/"))
        
        # Private RFC-1918 addresses
        self.assertFalse(is_safe_url("http://10.0.0.1/test.ics"))
        self.assertFalse(is_safe_url("http://192.168.1.1/cal.ics"))
        self.assertFalse(is_safe_url("http://172.16.0.1/cal.ics"))

    def test_sync_calendar_auth_enforcement(self):
        """Verify /api/calendar/sync rejects unauthenticated requests."""
        payload = {"ical_url": "https://example.com/calendar.ics"}
        res = self.client.post("/api/calendar/sync", data=json.dumps(payload))
        self.assertEqual(res.status_code, 401)

    def test_sync_calendar_empty_url_returns_default_events(self):
        """Verify empty URL returns existing or mock events without crashing."""
        payload = {"ical_url": ""}
        res = self.client.post(
            "/api/calendar/sync",
            data=json.dumps(payload),
            headers=self.valid_headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIn("events", data)
        self.assertTrue(len(data["events"]) > 0)

    def test_sync_calendar_with_db_events(self):
        """Verify previously saved calendar events are retrieved."""
        with self.db.write_transaction() as conn:
            conn.execute(
                "INSERT INTO calendar_events (title, start_time, end_time) VALUES (?, ?, ?)",
                ("Deep Work Block", "2026-08-16T14:00:00", "2026-08-16T16:00:00")
            )
        payload = {"ical_url": ""}
        res = self.client.post(
            "/api/calendar/sync",
            data=json.dumps(payload),
            headers=self.valid_headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(any(e["title"] == "Deep Work Block" for e in data["events"]))


if __name__ == "__main__":
    unittest.main()
