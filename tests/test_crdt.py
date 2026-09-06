"""
Test suite for MIND-FLOW Cognitive Productivity Tracker.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

"""
Unit tests for CRDT Multi-Device State Sync Engine (backend/crdt_sync.py).
Verifies formal CvRDT mathematical properties (commutativity, associativity, idempotency),
HLC monotonicity & clock skew convergence, LWW register/set behaviors, and multi-device sync engine.
"""

import sys
import os
import time
import threading
import unittest

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.crdt_sync import (
    HLCTimestamp,
    HybridLogicalClock,
    PNCounter,
    LWWRegister,
    LWWElementSet,
    CRDTSyncEngine
)


class TestHybridLogicalClock(unittest.TestCase):
    def test_hlc_monotonicity(self):
        hlc = HybridLogicalClock(node_id="node1")
        ts1 = hlc.now()
        ts2 = hlc.now()
        ts3 = hlc.now()

        self.assertTrue(ts1 < ts2)
        self.assertTrue(ts2 < ts3)
        self.assertEqual(ts1.node_id, "node1")

    def test_hlc_remote_update(self):
        hlc1 = HybridLogicalClock(node_id="node1")
        hlc2 = HybridLogicalClock(node_id="node2")

        ts1 = hlc1.now()
        # Simulate remote reasonable future timestamp (+10s)
        future_ts = HLCTimestamp(physical_time=ts1.physical_time + 10.0, logical_counter=5, node_id="node2")

        updated_ts = hlc1.update(future_ts)
        self.assertGreaterEqual(updated_ts.physical_time, future_ts.physical_time)
        self.assertTrue(updated_ts > ts1)

        # Simulate extreme future clock skew (+10000s) and verify clamping
        extreme_ts = HLCTimestamp(physical_time=ts1.physical_time + 10000.0, logical_counter=5, node_id="node2")
        clamped_ts = hlc1.update(extreme_ts)
        self.assertLess(clamped_ts.physical_time, extreme_ts.physical_time)

    def test_hlc_serialization(self):
        ts = HLCTimestamp(physical_time=1700000000.123, logical_counter=42, node_id="test_node")
        d = ts.to_dict()
        self.assertEqual(d["physical_time"], 1700000000.123)
        self.assertEqual(d["logical_counter"], 42)
        self.assertEqual(d["node_id"], "test_node")

        reconstructed = HLCTimestamp.from_dict(d)
        self.assertEqual(ts, reconstructed)

    def test_hlc_comparison_operators(self):
        ts_low = HLCTimestamp(100.0, 0, "a")
        ts_mid = HLCTimestamp(100.0, 1, "a")
        ts_high = HLCTimestamp(101.0, 0, "a")
        ts_node = HLCTimestamp(100.0, 0, "b")

        self.assertTrue(ts_low < ts_mid)
        self.assertTrue(ts_mid < ts_high)
        self.assertTrue(ts_low < ts_node)  # Tie broken by node_id 'a' < 'b'
        self.assertTrue(ts_low <= ts_low)
        self.assertTrue(ts_high > ts_low)
        self.assertEqual(ts_low, HLCTimestamp(100.0, 0, "a"))


class TestPNCounter(unittest.TestCase):
    def test_pn_counter_operations(self):
        counter = PNCounter()
        self.assertEqual(counter.value, 0)

        counter.increment("node1", 5)
        self.assertEqual(counter.value, 5)

        counter.decrement("node2", 2)
        self.assertEqual(counter.value, 3)

        counter.increment("node2", 10)
        self.assertEqual(counter.value, 13)

    def test_pn_counter_cvrdt_properties(self):
        a = PNCounter()
        a.increment("node1", 10)
        a.decrement("node2", 2)

        b = PNCounter()
        b.increment("node2", 5)
        b.increment("node3", 7)
        b.decrement("node1", 1)

        c = PNCounter()
        c.increment("node1", 2)
        c.decrement("node3", 3)

        # 1. Commutativity: Merge(A, B) == Merge(B, A)
        ab = a.merge(b)
        ba = b.merge(a)
        self.assertEqual(ab.value, ba.value)
        self.assertEqual(ab.to_dict(), ba.to_dict())

        # 2. Associativity: Merge(Merge(A, B), C) == Merge(A, Merge(B, C))
        ab_c = ab.merge(c)
        a_bc = a.merge(b.merge(c))
        self.assertEqual(ab_c.value, a_bc.value)
        self.assertEqual(ab_c.to_dict(), a_bc.to_dict())

        # 3. Idempotency: Merge(A, A) == A
        aa = a.merge(a)
        self.assertEqual(aa.value, a.value)
        self.assertEqual(aa.to_dict(), a.to_dict())

    def test_pn_counter_serialization(self):
        counter = PNCounter()
        counter.increment("node1", 15)
        counter.decrement("node2", 4)

        d = counter.to_dict()
        reconstructed = PNCounter.from_dict(d)
        self.assertEqual(reconstructed.value, 11)
        self.assertEqual(counter.value, reconstructed.value)


class TestLWWRegister(unittest.TestCase):
    def test_lww_register_set_and_merge(self):
        reg_a = LWWRegister(value="initial", timestamp=HLCTimestamp(100.0, 0, "nodeA"), node_id="nodeA")
        reg_b = LWWRegister(value="updated_later", timestamp=HLCTimestamp(101.0, 0, "nodeB"), node_id="nodeB")

        merged_ab = reg_a.merge(reg_b)
        self.assertEqual(merged_ab.value, "updated_later")

        merged_ba = reg_b.merge(reg_a)
        self.assertEqual(merged_ba.value, "updated_later")

    def test_lww_register_tie_breaker(self):
        # Same timestamp, different node_ids
        reg_a = LWWRegister(value="valA", timestamp=HLCTimestamp(100.0, 0, "nodeA"), node_id="nodeA")
        reg_b = LWWRegister(value="valB", timestamp=HLCTimestamp(100.0, 0, "nodeB"), node_id="nodeB")

        merged1 = reg_a.merge(reg_b)
        merged2 = reg_b.merge(reg_a)

        self.assertEqual(merged1.value, "valB")
        self.assertEqual(merged2.value, "valB")
        self.assertEqual(merged1.value, merged2.value)

    def test_lww_register_serialization(self):
        reg = LWWRegister(value={"battery": 88.5}, timestamp=HLCTimestamp(200.0, 1, "node1"), node_id="node1")
        d = reg.to_dict()
        reconstructed = LWWRegister.from_dict(d)
        self.assertEqual(reconstructed.value, {"battery": 88.5})
        self.assertEqual(reconstructed.node_id, "node1")


class TestLWWElementSet(unittest.TestCase):
    def test_lww_element_set_add_remove(self):
        s = LWWElementSet()
        ts1 = HLCTimestamp(100.0, 0, "node1")
        ts2 = HLCTimestamp(101.0, 0, "node1")

        s.add("item1", timestamp=ts1, node_id="node1")
        self.assertIn("item1", s.read())

        s.remove("item1", timestamp=ts2, node_id="node1")
        self.assertNotIn("item1", s.read())

    def test_lww_element_set_presence_bias(self):
        # Same timestamp for add and remove -> LWW presence bias keeps element
        s = LWWElementSet()
        ts = HLCTimestamp(100.0, 0, "node1")
        s.add("rule_code", timestamp=ts, node_id="node1")
        s.remove("rule_code", timestamp=ts, node_id="node1")

        self.assertIn("rule_code", s.read())

    def test_lww_element_set_merge_symmetry(self):
        s1 = LWWElementSet()
        s1.add("itemA", timestamp=HLCTimestamp(100.0, 0, "n1"), node_id="n1")
        s1.add("itemB", timestamp=HLCTimestamp(102.0, 0, "n1"), node_id="n1")

        s2 = LWWElementSet()
        s2.add("itemB", timestamp=HLCTimestamp(101.0, 0, "n2"), node_id="n2")
        s2.remove("itemA", timestamp=HLCTimestamp(105.0, 0, "n2"), node_id="n2")

        merged1 = s1.merge(s2)
        merged2 = s2.merge(s1)

        self.assertEqual(merged1.read(), merged2.read())
        self.assertNotIn("itemA", merged1.read())
        self.assertIn("itemB", merged1.read())

    def test_lww_element_set_serialization(self):
        s = LWWElementSet()
        s.add({"app": "VSCode", "category": "Work"}, timestamp=HLCTimestamp(10.0, 0, "n1"), node_id="n1")
        d = s.to_dict()

        reconstructed = LWWElementSet.from_dict(d)
        self.assertEqual(len(reconstructed.read_elements()), 1)
        self.assertEqual(reconstructed.read_elements()[0], {"app": "VSCode", "category": "Work"})


class TestCRDTSyncEngine(unittest.TestCase):
    def test_engine_multi_device_sync(self):
        device1 = CRDTSyncEngine(node_id="device_laptop")
        device2 = CRDTSyncEngine(node_id="device_desktop")

        # Device 1 updates battery & adds rules
        device1.update_stamina_battery(78.5)
        device1.add_category_rule({"pattern": "python.exe", "category": "Work"})
        device1.increment_counter("focus_sessions", 3)
        device1.add_session_log("sess_001", {"duration": 1800, "app": "PyCharm"})

        # Device 2 updates fatigue score & counter
        device2.update_fatigue_score(15.2)
        device2.add_category_rule({"pattern": "steam.exe", "category": "Rest"})
        device2.increment_counter("focus_sessions", 2)
        device2.increment_counter("break_sessions", 1)
        device2.add_session_log("sess_002", {"duration": 900, "app": "Spotify"})

        # Sync Device 1 -> Device 2
        state1 = device1.export_state()
        device2.merge_state(state1)

        # Sync Device 2 -> Device 1
        state2 = device2.export_state()
        device1.merge_state(state2)

        # Verify state convergence across both devices
        self.assertEqual(device1.get_stamina_battery(), 78.5)
        self.assertEqual(device2.get_stamina_battery(), 78.5)

        self.assertEqual(device1.get_fatigue_score(), 15.2)
        self.assertEqual(device2.get_fatigue_score(), 15.2)

        self.assertEqual(device1.get_counter_value("focus_sessions"), 5)
        self.assertEqual(device2.get_counter_value("focus_sessions"), 5)

        self.assertEqual(device1.get_counter_value("break_sessions"), 1)
        self.assertEqual(device2.get_counter_value("break_sessions"), 1)

        self.assertEqual(len(device1.get_category_rules()), 2)
        self.assertEqual(len(device2.get_category_rules()), 2)

        self.assertEqual(len(device1.get_session_logs()), 2)
        self.assertEqual(len(device2.get_session_logs()), 2)

    def test_engine_serialization_roundtrip(self):
        engine = CRDTSyncEngine(node_id="main_node")
        engine.update_stamina_battery(92.0)
        engine.update_fatigue_score(8.0)
        engine.increment_counter("steps", 1200)
        engine.add_category_rule("rule_1")

        dict_repr = engine.to_dict()
        reconstructed = CRDTSyncEngine.from_dict(dict_repr)

        self.assertEqual(reconstructed.node_id, "main_node")
        self.assertEqual(reconstructed.get_stamina_battery(), 92.0)
        self.assertEqual(reconstructed.get_fatigue_score(), 8.0)
        self.assertEqual(reconstructed.get_counter_value("steps"), 1200)
        self.assertEqual(reconstructed.get_category_rules(), ["rule_1"])

    def test_hlc_concurrent_threads(self):
        import threading
        hlc = HybridLogicalClock(node_id="concurrent_node")
        timestamps = []
        lock = threading.Lock()

        def worker():
            for _ in range(100):
                ts = hlc.now()
                with lock:
                    timestamps.append(ts)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(timestamps), 1000)
        # Verify all timestamps are unique
        unique_tuples = set(ts.to_tuple() for ts in timestamps)
        self.assertEqual(len(unique_tuples), 1000)

    def test_crdt_setters_preserve_explicit_timestamps(self):
        engine = CRDTSyncEngine(node_id="local_node")
        explicit_ts = HLCTimestamp(physical_time=time.time() + 1000.0, logical_counter=7, node_id="remote_node")

        # 1. update_stamina_battery
        engine.update_stamina_battery(85.0, timestamp=explicit_ts)
        self.assertEqual(engine.stamina_battery.timestamp, explicit_ts)
        self.assertEqual(engine.stamina_battery.node_id, "remote_node")

        # 2. update_fatigue_score
        engine.update_fatigue_score(12.0, timestamp=explicit_ts)
        self.assertEqual(engine.fatigue_score.timestamp, explicit_ts)
        self.assertEqual(engine.fatigue_score.node_id, "remote_node")

        # 3. update_battery_state
        engine.update_battery_state(90.0, timestamp=explicit_ts)
        self.assertEqual(engine.stamina_battery.timestamp, explicit_ts)

        # 4. add_category_rule & set_category_rule
        rule = {"pattern": "python.exe", "category": "Work"}
        engine.add_category_rule(rule, timestamp=explicit_ts)
        self.assertEqual(engine.category_rules.add_set[engine.category_rules._element_key(rule)], explicit_ts)

        rule2 = {"pattern": "game.exe", "category": "Rest"}
        engine.set_category_rule(rule2, timestamp=explicit_ts)
        self.assertEqual(engine.category_rules.add_set[engine.category_rules._element_key(rule2)], explicit_ts)

        # 5. remove_category_rule
        engine.remove_category_rule(rule, timestamp=explicit_ts)
        self.assertEqual(engine.category_rules.remove_set[engine.category_rules._element_key(rule)], explicit_ts)

    def test_concurrent_bidirectional_merge_no_deadlock(self):
        """Stress test: 10 threads continuously merging two CRDTSyncEngines bidirectionally."""
        engine_a = CRDTSyncEngine(node_id="node_A")
        engine_b = CRDTSyncEngine(node_id="node_B")

        # Populate some initial data
        engine_a.update_stamina_battery(75.0)
        engine_b.update_stamina_battery(80.0)
        engine_a.add_category_rule({"pattern": "code.exe", "category": "Work"})
        engine_b.add_category_rule({"pattern": "spotify.exe", "category": "Rest"})

        stop_event = threading.Event()
        errors = []

        def worker_merge_a_into_b():
            try:
                for _ in range(50):
                    if stop_event.is_set():
                        break
                    engine_b.merge_state(engine_a)
                    engine_a.update_stamina_battery(70.0 + (_ % 10))
            except Exception as e:
                errors.append(e)

        def worker_merge_b_into_a():
            try:
                for _ in range(50):
                    if stop_event.is_set():
                        break
                    engine_a.merge_state(engine_b)
                    engine_b.update_stamina_battery(80.0 + (_ % 10))
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(5):
            t1 = threading.Thread(target=worker_merge_a_into_b)
            t2 = threading.Thread(target=worker_merge_b_into_a)
            threads.extend([t1, t2])

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=5.0)
            self.assertFalse(t.is_alive(), "CRDT merge deadlocked!")

        self.assertEqual(len(errors), 0, f"Errors during concurrent merge: {errors}")


if __name__ == '__main__':
    unittest.main()


