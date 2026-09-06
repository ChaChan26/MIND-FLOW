"""
Headless Chrome End-to-End Frontend DOM & Runtime Verification Suite.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import time
import socket
import threading
import subprocess
import shutil
import unittest

os.environ["MINDFLOW_DB_FILE"] = ":memory:"
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.server import run_server, SHARED_API_TOKEN

def find_chrome_path():
    try:
        import winreg
        import shutil as sht
        for hkey in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hkey, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val and os.path.exists(val):
                        return val
            except OSError:
                pass

        path = sht.which("chrome") or sht.which("chrome.exe")
        if path and os.path.exists(path):
            return path

        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for p in [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]:
            if p:
                paths.append(os.path.join(p, "Google", "Chrome", "Application", "chrome.exe"))
                paths.append(os.path.join(p, "Chromium", "Application", "chrome.exe"))

        for p in paths:
            if os.path.exists(p):
                return p
    except Exception:
        pass
    return None

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

class TestChromeFrontend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chrome_path = find_chrome_path()
        cls.port = get_free_port()
        cls.server_thread = threading.Thread(
            target=run_server,
            kwargs={"port": cls.port},
            daemon=True
        )
        cls.server_thread.start()
        time.sleep(1.2)

    def test_find_chrome_path_capability(self):
        """Verify chrome detection utility finds valid executable."""
        if self.chrome_path:
            self.assertTrue(os.path.exists(self.chrome_path))

    def test_headless_chrome_full_react_dom_render(self):
        """Execute real headless Chrome against live Flask backend and verify React DOM mounts without ErrorBoundary."""
        if not self.chrome_path:
            self.skipTest("Chrome executable not found on host machine.")

        temp_profile = os.path.join(os.environ.get("TEMP", "C:/Temp"), f"mind_chrome_{int(time.time())}")
        os.makedirs(temp_profile, exist_ok=True)

        try:
            # 1. Test Initial Launch (Onboarding or Dashboard)
            url = f"http://127.0.0.1:{self.port}/?token={SHARED_API_TOKEN}"
            cmd = [
                self.chrome_path,
                "--headless=new",
                "--disable-gpu",
                f"--user-data-dir={temp_profile}",
                "--virtual-time-budget=3000",
                "--dump-dom",
                url
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            self.assertEqual(proc.returncode, 0, f"Chrome exited with error: {proc.stderr}")
            dom = proc.stdout

            self.assertIn('<div id="root">', dom, "React failed to mount #root container.")
            self.assertNotIn("Something went wrong rendering this view", dom, "React ErrorBoundary caught an unhandled exception!")

            # 2. Test all sub-screens
            for screen in ["dashboard", "zen", "analytics", "achievements", "preferences"]:
                screen_url = f"http://127.0.0.1:{self.port}/?token={SHARED_API_TOKEN}&screen={screen}"
                cmd_screen = [
                    self.chrome_path,
                    "--headless=new",
                    "--disable-gpu",
                    f"--user-data-dir={temp_profile}",
                    "--virtual-time-budget=3000",
                    "--dump-dom",
                    screen_url
                ]
                proc_screen = subprocess.run(cmd_screen, capture_output=True, text=True, timeout=20)
                self.assertEqual(proc_screen.returncode, 0, f"Chrome screen navigation failed on {screen}: {proc_screen.stderr}")
                screen_dom = proc_screen.stdout
                self.assertNotIn("Something went wrong rendering this view", screen_dom, f"Screen '{screen}' triggered ErrorBoundary!")
        finally:
            shutil.rmtree(temp_profile, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()

