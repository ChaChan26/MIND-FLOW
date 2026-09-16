"""
Unit tests for App Categorization & Recategorization Fixes

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import unittest
import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import MindFlowDB
from backend.task_classifier import TaskClassifier
from app import classify_activity_mode


class TestAppCategorizationFixes(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_mindflow.db")
        self.db = MindFlowDB(db_path=self.db_path)
        TaskClassifier.clear_cache()

    def tearDown(self):
        self.db.close()
        self.tmp_dir.cleanup()

    def test_recategorize_deduplication(self):
        """Ensure recategorizing an app cleans it from all other keyword lists."""
        self.db.update_settings({
            "work_keywords": ["shellexperiencehost.exe", "vscode"],
            "recharge_keywords": ["youtube"],
            "neutral_keywords": []
        })

        # Recategorize to recharge
        self.db.recategorize_app("shellexperiencehost.exe", "recharge")
        
        settings = self.db.get_settings()
        self.assertNotIn("shellexperiencehost.exe", settings.get("work_keywords", []))
        self.assertIn("shellexperiencehost.exe", settings.get("recharge_keywords", []))
        self.assertNotIn("shellexperiencehost.exe", settings.get("neutral_keywords", []))

        # Recategorize to neutral
        self.db.recategorize_app("shellexperiencehost.exe", "neutral")
        settings = self.db.get_settings()
        self.assertNotIn("shellexperiencehost.exe", settings.get("work_keywords", []))
        self.assertNotIn("shellexperiencehost.exe", settings.get("recharge_keywords", []))
        self.assertIn("shellexperiencehost.exe", settings.get("neutral_keywords", []))

    def test_anime_and_entertainment_browser_classification(self):
        """Ensure watching anime on Chrome is classified as recharge."""
        work_kw = ["vs code", "github", "rstudio.exe"]
        recharge_kw = ["youtube", "facebook", "hades.exe"]
        neutral_kw = []

        cat = classify_activity_mode(
            "chrome.exe",
            "Tập 01 Cuộc Chiến Tỏ Tình (Kaguya-sama: Love is War)",
            work_kw,
            recharge_kw,
            [],
            neutral_kw
        )
        self.assertEqual(cat, "recharge")

    def test_hardware_toolkit_neutral_classification(self):
        """Ensure system utilities like Lenovo Legion Toolkit default to neutral."""
        work_kw = ["vs code", "github"]
        recharge_kw = ["youtube", "hades.exe"]
        neutral_kw = []

        cat = classify_activity_mode(
            "lenovo legion toolkit.exe",
            "Lenovo Legion Toolkit",
            work_kw,
            recharge_kw,
            [],
            neutral_kw
        )
        self.assertEqual(cat, "neutral")

    def test_custom_user_override_precedence(self):
        """Ensure user-defined keyword rules take absolute precedence."""
        work_kw = ["customtool.exe"]
        recharge_kw = ["slack.exe"] # normally work, but user put it in recharge
        neutral_kw = []

        cat = classify_activity_mode(
            "slack.exe",
            "Slack | General Channel",
            work_kw,
            recharge_kw,
            [],
            neutral_kw
        )
        self.assertEqual(cat, "recharge")


if __name__ == "__main__":
    unittest.main()
