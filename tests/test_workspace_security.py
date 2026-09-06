"""
Test suite for MIND-FLOW Cognitive Productivity Tracker.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

os.environ["MINDFLOW_DB_FILE"] = ":memory:"
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.workspace_manager import WorkspaceManager

class TestWorkspaceSecurityBounds(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.mgr = WorkspaceManager(self.test_dir)
        self.mgr.desktop_dir = os.path.join(self.test_dir, "MockDesktop")
        os.makedirs(self.mgr.desktop_dir, exist_ok=True)

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    def test_path_traversal_rejection(self):
        """Verify _safe_path raises ValueError on traversal sequences and path escapes."""
        invalid_filenames = [
            "../etc/passwd",
            "..\\Windows\\System32\\cmd.exe",
            "subfolder/file.txt",
            "subfolder\\file.txt",
            ".",
            "..",
            "",
            "/absolute/path/file.txt",
            "C:\\Windows\\System32\\cmd.exe"
        ]
        for bad_name in invalid_filenames:
            with self.subTest(filename=bad_name):
                with self.assertRaises(ValueError):
                    self.mgr._safe_path(self.mgr.desktop_dir, bad_name)

    def test_valid_filename_resolution(self):
        """Verify _safe_path resolves legitimate filenames within parent directory."""
        resolved = self.mgr._safe_path(self.mgr.desktop_dir, "valid_shortcut.lnk")
        expected = os.path.abspath(os.path.join(self.mgr.desktop_dir, "valid_shortcut.lnk"))
        self.assertEqual(resolved, expected)

    def test_safe_move_backup_retention(self):
        """Verify _safe_move creates a timestamped backup instead of overwriting destination."""
        src = os.path.join(self.test_dir, "source.txt")
        dst = os.path.join(self.test_dir, "dest.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("new content")
        with open(dst, "w", encoding="utf-8") as f:
            f.write("original content")

        self.mgr._safe_move(src, dst)

        # Verify dest has new content
        with open(dst, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "new content")

        # Verify backup file exists containing original content
        backups = [f for f in os.listdir(self.test_dir) if f.startswith("dest.txt.bak.")]
        self.assertEqual(len(backups), 1)
        with open(os.path.join(self.test_dir, backups[0]), "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "original content")

    def test_profile_isolation_and_readme_protection(self):
        """Verify Work and Recharge profile swapping preserves readmes and isolates files."""
        work_dir = os.path.join(self.mgr.profiles_dir, "Work")
        recharge_dir = os.path.join(self.mgr.profiles_dir, "Recharge")

        with open(os.path.join(work_dir, "Work_Readme.txt"), "w", encoding="utf-8") as f:
            f.write("work readme")
        with open(os.path.join(work_dir, "work_app.lnk"), "w", encoding="utf-8") as f:
            f.write("work link")
        with open(os.path.join(recharge_dir, "Recharge_Readme.txt"), "w", encoding="utf-8") as f:
            f.write("recharge readme")
        with open(os.path.join(recharge_dir, "game.lnk"), "w", encoding="utf-8") as f:
            f.write("game link")

        # Transition to work mode
        self.mgr.transition_workspace("neutral", "work")

        # Desktop should contain work_app.lnk but NOT Work_Readme.txt or game.lnk
        self.assertTrue(os.path.exists(os.path.join(self.mgr.desktop_dir, "work_app.lnk")))
        self.assertFalse(os.path.exists(os.path.join(self.mgr.desktop_dir, "Work_Readme.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.mgr.desktop_dir, "game.lnk")))

    def test_cloud_sync_detection_safety(self):
        """Verify cloud sync detection flags cloud provider paths and disables physical operations."""
        original_desktop = self.mgr.desktop_dir
        try:
            cloud_paths = [
                r"C:\Users\TestUser\OneDrive\Desktop",
                r"C:\Users\TestUser\Google Drive\Desktop",
                r"C:\Users\TestUser\Dropbox\Desktop",
                r"C:\Users\TestUser\iCloud\Desktop",
                r"C:\Users\TestUser\Creative Cloud\Desktop"
            ]
            for path in cloud_paths:
                with self.subTest(path=path):
                    self.mgr.desktop_dir = path
                    self.assertTrue(self.mgr.detect_cloud_sync())

            self.mgr.desktop_dir = r"C:\Users\TestUser\Desktop"
            self.assertFalse(self.mgr.detect_cloud_sync())

            # Test that when is_cloud_sync is True, workspace operations skip physical file moves safely
            self.mgr.is_cloud_sync = True
            self.mgr.transition_workspace("neutral", "work")
            self.mgr.sweep_back_all()
            self.mgr.recover_stranded_files()
        finally:
            self.mgr.desktop_dir = original_desktop
            self.mgr.is_cloud_sync = self.mgr.detect_cloud_sync()

    def test_crash_recovery_manifest_lifecycle(self):
        """Verify stranded manifest writing, recovery execution, and manifest clearing."""
        src_file = os.path.join(self.test_dir, "stranded.lnk")
        dst_file = os.path.join(self.mgr.desktop_dir, "stranded.lnk")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("stranded shortcut")

        moves = [{"src": src_file, "dst": dst_file}]
        self.mgr._write_manifest(moves)
        self.assertTrue(os.path.exists(self.mgr.manifest_path))

        # Trigger recovery
        self.mgr.recover_stranded_files()
        self.assertTrue(os.path.exists(dst_file))
        self.assertFalse(os.path.exists(self.mgr.manifest_path))

    def test_permission_error_resilience(self):
        """Verify _execute_moves handles PermissionError gracefully on locked files without crashing."""
        src = os.path.join(self.test_dir, "locked_src.txt")
        dst = os.path.join(self.test_dir, "locked_dst.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("content")

        with patch("shutil.move", side_effect=PermissionError("File locked by process")):
            success, completed = self.mgr._execute_moves([{"src": src, "dst": dst}])
            self.assertFalse(success)
            self.assertEqual(completed, [])
            # Manifest should retain the failed move
            self.assertTrue(os.path.exists(self.mgr.manifest_path))
            with open(self.mgr.manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
                self.assertEqual(len(manifest_data), 1)
                self.assertEqual(manifest_data[0]["src"], src)

    def test_backup_unique_timestamp_naming(self):
        """Verify _safe_move generates timestamped backup names matching dest.txt.bak.<timestamp>."""
        src = os.path.join(self.test_dir, "src_unique.txt")
        dst = os.path.join(self.test_dir, "dst_unique.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("new version")
        with open(dst, "w", encoding="utf-8") as f:
            f.write("v1")

        self.mgr._safe_move(src, dst)

        backups = [f for f in os.listdir(self.test_dir) if ".bak." in f]
        self.assertTrue(len(backups) >= 1)
        timestamp_part = backups[0].split(".bak.")[1]
        self.assertTrue(timestamp_part.split("_")[0].isdigit())

        # Second move over existing dst file
        src2 = os.path.join(self.test_dir, "src_unique2.txt")
        with open(src2, "w", encoding="utf-8") as f:
            f.write("v3")
        self.mgr._safe_move(src2, dst)
        with open(dst, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "v3")

    def test_safe_move_rollback_on_failure(self):
        """Verify _safe_move restores the original destination file if shutil.move raises an error."""
        src = os.path.join(self.test_dir, "src_fail.txt")
        dst = os.path.join(self.test_dir, "dst_preserve.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("failed move content")
        with open(dst, "w", encoding="utf-8") as f:
            f.write("original preserved content")

        with patch("shutil.move", side_effect=PermissionError("Simulated write lock failure")):
            with self.assertRaises(PermissionError):
                self.mgr._safe_move(src, dst)

        # Ensure dst was restored via rollback
        self.assertTrue(os.path.exists(dst))
        with open(dst, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "original preserved content")

    def test_safe_path_case_insensitivity(self):
        """Verify _safe_path handles casing differences across drive letters/paths on Windows."""
        parent = os.path.abspath(self.mgr.desktop_dir)
        # Toggle parent case simulation
        parent_upper = parent.upper()
        resolved = self.mgr._safe_path(parent_upper, "my_file.txt")
        self.assertTrue(os.path.normcase(resolved).startswith(os.path.normcase(parent)))

if __name__ == "__main__":
    unittest.main()


