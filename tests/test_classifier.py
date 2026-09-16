"""
Test suite for MIND-FLOW Cognitive Productivity Tracker.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import time
import unittest

os.environ["MINDFLOW_DB_FILE"] = ":memory:"
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.task_classifier import TaskClassifier, classify, get_stats, CATEGORY_WORK, CATEGORY_REST, CATEGORY_NEUTRAL


class TestTaskClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = TaskClassifier(lru_maxsize=500, worker_count=2)

    def test_tier1_lru_cache_hit(self):
        proc = "code.exe"
        title = "main.py - MIND-FLOW - Visual Studio Code"

        # 1st call -> Tier 2 hit, cached in Tier 1
        res1 = self.classifier.classify(proc, title)
        self.assertEqual(res1, CATEGORY_WORK)

        # 2nd call -> Tier 1 LRU hit
        res2 = self.classifier.classify(proc, title)
        self.assertEqual(res2, CATEGORY_WORK)

        stats = self.classifier.get_stats()
        self.assertEqual(stats["tier1_hits"], 1)
        self.assertGreaterEqual(stats["total_classifications"], 2)
        self.assertGreater(stats["tier1_hit_rate"], 0.0)

    def test_clear_cache(self):
        proc = "code.exe"
        title = "main.py - VS Code"
        self.classifier.classify(proc, title)
        self.classifier.classify(proc, title)
        self.assertGreater(self.classifier.get_stats()["lru_cache_size"], 0)

        self.classifier.clear_cache()
        stats = self.classifier.get_stats()
        self.assertEqual(stats["lru_cache_size"], 0)
        self.assertEqual(stats["tier1_hits"], 0)
        self.assertEqual(stats["total_classifications"], 0)

    def test_tier2_classification_accuracy(self):
        work_samples = [
            ("code.exe", "main.py - VS Code"),
            ("pycharm64.exe", "database.py - PyCharm"),
            ("chrome.exe", "Stack Overflow - How to optimize Python GIL"),
            ("chrome.exe", "GitHub - repository/commit"),
            ("word.exe", "Project_Report.docx - Microsoft Word"),
            ("powershell.exe", "Windows PowerShell"),
        ]

        rest_samples = [
            ("steam.exe", "Steam Store"),
            ("vlc.exe", "Movie_720p.mkv - VLC media player"),
            ("chrome.exe", "YouTube - Lofi Hip Hop Stream"),
            ("spotify.exe", "Spotify Free"),
            ("discord.exe", "Discord - #general"),
        ]

        neutral_samples = [
            ("explorer.exe", "File Explorer"),
            ("taskmgr.exe", "Task Manager"),
            ("calc.exe", "Calculator"),
        ]

        for proc, title in work_samples:
            cat = self.classifier.classify(proc, title)
            self.assertEqual(cat, CATEGORY_WORK, f"Expected 'work' for {proc} / {title}, got '{cat}'")

        for proc, title in rest_samples:
            cat = self.classifier.classify(proc, title)
            self.assertEqual(cat, CATEGORY_REST, f"Expected 'rest' for {proc} / {title}, got '{cat}'")

        for proc, title in neutral_samples:
            cat = self.classifier.classify(proc, title)
            self.assertEqual(cat, CATEGORY_NEUTRAL, f"Expected 'neutral' for {proc} / {title}, got '{cat}'")

    def test_tier3_ambiguous_and_async_enrichment(self):
        tc = TaskClassifier(lru_maxsize=100, worker_count=1)
        ambiguous_proc = "xyz_unknown_proc.exe"
        ambiguous_title = "98765_random_title_qwerty"

        cat = tc.classify(ambiguous_proc, ambiguous_title)
        self.assertIn(cat, [CATEGORY_WORK, CATEGORY_REST, CATEGORY_NEUTRAL])

        stats = tc.get_stats()
        self.assertGreaterEqual(stats["tier3_hits"], 1)

        # Allow background worker to process item
        time.sleep(0.2)

        # Submitting the exact same item should now hit Tier 1 cache populated by Tier 3 worker
        cat2 = tc.classify(ambiguous_proc, ambiguous_title)
        self.assertIn(cat2, [CATEGORY_WORK, CATEGORY_REST, CATEGORY_NEUTRAL])

    def test_latency_benchmark_sla(self):
        tc = TaskClassifier(lru_maxsize=2000, worker_count=2)
        sample_pool = [
            ("code.exe", "task_classifier.py - VS Code"),
            ("chrome.exe", "YouTube - Music Video"),
            ("explorer.exe", "C:\\MIND\\backend"),
            ("pycharm64.exe", "test_classifier.py"),
            ("spotify.exe", "Spotify"),
        ]

        # Warm up cache with sample pool
        for proc, title in sample_pool:
            tc.classify(proc, title)

        # Run 10,000 ticks benchmark
        num_ticks = 10000
        latencies = []

        start_total = time.perf_counter()
        for i in range(num_ticks):
            proc, title = sample_pool[i % len(sample_pool)]
            t0 = time.perf_counter()
            tc.classify(proc, title)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)  # ms
        total_time_ms = (time.perf_counter() - start_total) * 1000.0

        avg_latency_ms = total_time_ms / num_ticks
        latencies.sort()
        p99_latency_ms = latencies[int(num_ticks * 0.99)]

        print(f"\n[Classifier Benchmark] 10,000 Ticks: Total={total_time_ms:.2f}ms, Avg={avg_latency_ms:.4f}ms, P99={p99_latency_ms:.4f}ms")

        # SLA Assertions: Average < 0.1ms, P99 < 1.0ms
        self.assertLess(avg_latency_ms, 0.1, f"Average latency {avg_latency_ms:.4f}ms exceeded SLA threshold of 0.1ms")
        self.assertLess(p99_latency_ms, 1.0, f"P99 latency {p99_latency_ms:.4f}ms exceeded SLA threshold of 1.0ms")

    def test_long_title_truncation(self):
        long_title = "vs code " + ("a" * 10000)
        cat = self.classifier.classify("code.exe", long_title)
        self.assertEqual(cat, CATEGORY_WORK)

    def test_get_stats_metrics(self):
        stats = get_stats()
        expected_keys = {
            "tier1_hits", "tier2_hits", "tier3_hits", "total_classifications",
            "tier1_hit_rate", "tier2_hit_rate", "tier3_hit_rate", "lru_cache_size", "lru_maxsize"
        }
        self.assertTrue(expected_keys.issubset(stats.keys()))


if __name__ == "__main__":
    unittest.main()
