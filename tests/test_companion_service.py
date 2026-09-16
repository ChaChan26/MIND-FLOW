"""
Unit tests for companion service and CBT messaging logic.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import unittest
from backend.companion_service import generate_companion_message, calculate_battery_forecast


class TestCompanionService(unittest.TestCase):
    """Test suite for companion message generation and scale handling."""

    def test_battery_critical_at_low_percentage(self):
        """Verify that 4.0% capacity on a 0-100 scale correctly triggers battery critical alert."""
        msg = generate_companion_message(
            tracking_active=True,
            today_bypasses=0,
            high_stress_alert=False,
            latest_mood=None,
            current_energy=4.0,  # 4% on 0-100 scale
            cur_mode="work"
        )
        self.assertIn("Battery critical", msg)
        self.assertIn("Zen Space", msg)

    def test_battery_critical_boundary(self):
        """Verify that 40.0% or lower triggers battery critical alert."""
        msg = generate_companion_message(
            tracking_active=True,
            today_bypasses=0,
            high_stress_alert=False,
            latest_mood=None,
            current_energy=40.0,
            cur_mode="work"
        )
        self.assertIn("Battery critical", msg)

    def test_battery_medium_energy(self):
        """Verify that 50.0% energy triggers medium energy guidance."""
        msg = generate_companion_message(
            tracking_active=True,
            today_bypasses=0,
            high_stress_alert=False,
            latest_mood=None,
            current_energy=50.0,
            cur_mode="work"
        )
        self.assertIn("Medium energy", msg)

    def test_legacy_scale_explicit_conversion(self):
        """Verify that is_legacy_scale=True correctly maps 1-5 scale to 0-100."""
        # 4.0 on a 1-5 scale is 80% (optimal)
        msg = generate_companion_message(
            tracking_active=True,
            today_bypasses=0,
            high_stress_alert=False,
            latest_mood=None,
            current_energy=4.0,
            cur_mode="work",
            is_legacy_scale=True
        )
        # On 80%, cur_mode="work" returns focus session advice, NOT battery critical
        self.assertNotIn("Battery critical", msg)
        self.assertIn("Focus session active", msg)

    def test_tracking_paused_message(self):
        """Verify paused message when tracking is inactive."""
        msg = generate_companion_message(
            tracking_active=False,
            today_bypasses=0,
            high_stress_alert=False,
            latest_mood=None,
            current_energy=100.0,
            cur_mode="work"
        )
        self.assertIn("Companion is paused", msg)

    def test_mood_interventions(self):
        """Verify mood-based CBT advice is prioritized over energy levels."""
        msg = generate_companion_message(
            tracking_active=True,
            today_bypasses=0,
            high_stress_alert=False,
            latest_mood="anxious",
            current_energy=90.0,
            cur_mode="work"
        )
        self.assertIn("Anxious mood logged", msg)

    def test_battery_forecast(self):
        """Verify depletion and recharge forecast strings."""
        work_forecast = calculate_battery_forecast(
            cur_mode="work",
            battery_cap=50.0,
            adaptive_rest_limit_seconds=120
        )
        self.assertIn("Battery will deplete in ~100 minutes", work_forecast)

        recharge_forecast = calculate_battery_forecast(
            cur_mode="recharge",
            battery_cap=50.0,
            adaptive_rest_limit_seconds=120
        )
        self.assertIn("Fully charged battery expected in ~20 minutes", recharge_forecast)


if __name__ == "__main__":
    unittest.main()
