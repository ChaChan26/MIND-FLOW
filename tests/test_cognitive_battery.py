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

from app import CognitiveBattery
from backend.database import MindFlowDB

class TestCognitiveBatteryEngine(unittest.TestCase):
    def setUp(self):
        self.battery = CognitiveBattery(capacity=100.0, consecutive_work=0.0)

    def test_initialization_bounds_and_type_safety(self):
        """Verify initialization clamps capacity between 0 and 100 and handles invalid types."""
        # Over-capacity and negative streak
        b1 = CognitiveBattery(capacity=150.0, consecutive_work=-10.0)
        self.assertEqual(b1.capacity, 100.0)
        self.assertEqual(b1.consecutive_work_minutes, -10.0)

        # Under-capacity and invalid type
        b2 = CognitiveBattery(capacity=-20.0, consecutive_work="invalid")
        self.assertEqual(b2.capacity, 0.0)
        self.assertEqual(b2.consecutive_work_minutes, 0.0)

        # String inputs that convert to floats
        b3 = CognitiveBattery(capacity="75.5", consecutive_work="12.5")
        self.assertEqual(b3.capacity, 75.5)
        self.assertEqual(b3.consecutive_work_minutes, 12.5)

        # None values fallback safely
        b4 = CognitiveBattery(capacity=None, consecutive_work=None)
        self.assertEqual(b4.capacity, 100.0)
        self.assertEqual(b4.consecutive_work_minutes, 0.0)

    def test_work_mode_drain_and_fatigue_multiplier(self):
        """Verify drain math under work mode with fatigue escalation."""
        # 10 minutes of work starting at 0 streak
        # penalty = 1.0 + (10.0 * 0.035) = 1.35
        # drain = 0.5 * 1.35 * 10.0 = 6.75
        # capacity = 100.0 - 6.75 = 93.25
        cap, streak = self.battery.process_tick(is_working=True, elapsed_minutes=10.0, mode="work")
        self.assertEqual(streak, 10.0)
        self.assertAlmostEqual(cap, 93.25, places=4)

        # Another 10 minutes of work starting at 10 streak
        # streak becomes 20.0
        # penalty = 1.0 + (20.0 * 0.035) = 1.70
        # drain = 0.5 * 1.70 * 10.0 = 8.5
        # capacity = 93.25 - 8.5 = 84.75
        cap, streak = self.battery.process_tick(is_working=True, elapsed_minutes=10.0, mode="work")
        self.assertEqual(streak, 20.0)
        self.assertAlmostEqual(cap, 84.75, places=4)

    def test_rest_mode_recharge_and_streak_decay(self):
        """Verify rest mode recovers capacity at 2.5/min and decays streak at 3.0x rate."""
        b = CognitiveBattery(capacity=90.0, consecutive_work=10.0)
        # 2 minutes of rest:
        # streak = 10.0 - (2.0 * 3.0) = 4.0
        # recovery = 2.5 * 2.0 = 5.0 -> cap = 95.0
        cap, streak = b.process_tick(is_working=False, elapsed_minutes=2.0, mode="rest")
        self.assertEqual(streak, 4.0)
        self.assertAlmostEqual(cap, 95.0, places=4)

        # Another 2 minutes of rest: streak clamps to 0.0, capacity reaches 100.0 max
        cap, streak = b.process_tick(is_working=False, elapsed_minutes=2.0, mode="rest")
        self.assertEqual(streak, 0.0)
        self.assertAlmostEqual(cap, 100.0, places=4)

    def test_neutral_mode_preserves_state(self):
        """Verify neutral mode freezes capacity and consecutive work streak."""
        b = CognitiveBattery(capacity=82.5, consecutive_work=15.0)
        cap, streak = b.process_tick(is_working=False, elapsed_minutes=5.0, mode="neutral")
        self.assertEqual(cap, 82.5)
        self.assertEqual(streak, 15.0)

    def test_boundary_clamping_floors_and_ceilings(self):
        """Verify capacity never drops below 0.0 or exceeds 100.0."""
        # Extreme drain
        b_low = CognitiveBattery(capacity=5.0, consecutive_work=100.0)
        cap, _ = b_low.process_tick(is_working=True, elapsed_minutes=60.0, mode="work")
        self.assertEqual(cap, 0.0)

        # Extreme recharge
        b_high = CognitiveBattery(capacity=98.0, consecutive_work=0.0)
        cap, _ = b_high.process_tick(is_working=False, elapsed_minutes=20.0, mode="recharge")
        self.assertEqual(cap, 100.0)

    def test_database_battery_state_persistence(self):
        """Verify DB battery state retrieval and flushing."""
        db = MindFlowDB()
        try:
            with db.connection() as conn:
                conn.execute("UPDATE battery_state SET current_capacity = 100.0, consecutive_work_minutes = 0.0 WHERE id = 1")

            state = db.get_battery_state()
            self.assertEqual(state["capacity"], 100.0)
            self.assertEqual(state["consecutive_work"], 0.0)

            db.flush_battery_state(88.0, 14.5)
            state = db.get_battery_state()
            self.assertEqual(state["capacity"], 88.0)
            self.assertEqual(state["consecutive_work"], 14.5)
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
