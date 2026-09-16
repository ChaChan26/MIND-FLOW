"""
Comprehensive unit tests for /api/analytics/digest endpoint.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

from datetime import datetime, date, timedelta
from tests.test_base import BaseMindFlowTestCase


class TestAnalyticsDigestEndpoint(BaseMindFlowTestCase):

    def test_digest_default_weekly(self):
        """GET /api/analytics/digest defaults to weekly range."""
        resp = self.client.get("/api/analytics/digest", headers=self.get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("title"), "Weekly Cognitive Digest")
        self.assertEqual(data.get("range"), "weekly")
        self.assertIn("total_focus_hours", data)
        self.assertIn("recommendations", data)

    def test_digest_daily_range(self):
        """GET /api/analytics/digest?range=daily returns daily scope."""
        resp = self.client.get("/api/analytics/digest?range=daily", headers=self.get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("title"), "Daily Cognitive Digest")
        self.assertEqual(data.get("range"), "daily")

    def test_digest_monthly_range(self):
        """GET /api/analytics/digest?range=monthly returns monthly scope."""
        resp = self.client.get("/api/analytics/digest?range=monthly", headers=self.get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("title"), "Monthly Cognitive Digest")
        self.assertEqual(data.get("range"), "monthly")

    def test_digest_with_logged_sessions(self):
        """GET /api/analytics/digest calculates hours and recommendations accurately."""
        now = datetime.now()
        start = now - timedelta(seconds=3600)
        # Insert a 1-hour work session and a 30-minute recharge session
        self.db.log_session(
            mode="work",
            start_time=start,
            end_time=now,
            brain_dump="Built comprehensive testing suite",
            bypassed=False,
            is_flow=True,
            flow_duration=1800
        )
        recharge_start = now - timedelta(seconds=1800)
        self.db.log_session(
            mode="recharge",
            start_time=recharge_start,
            end_time=now,
            brain_dump=None,
            bypassed=False
        )

        resp = self.client.get("/api/analytics/digest?range=daily", headers=self.get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("total_focus_hours"), 1.0)
        self.assertEqual(data.get("total_recovery_hours"), 0.5)
        self.assertIn("Built comprehensive testing suite", data.get("accomplishments", []))

    def test_digest_auth_required(self):
        """Endpoint enforces @require_api_token and @require_local_origin."""
        resp = self.client.get("/api/analytics/digest")
        self.assertEqual(resp.status_code, 401)
