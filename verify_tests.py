import os
import shutil
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from backend.database import MindFlowDB
from backend.workspace import WorkspaceManager
import time
import subprocess
import webbrowser
from app import get_active_window_title, get_active_process_name, get_idle_seconds, matches_keyword, shared_state, launch_app_window, trigger_lockout_overlay
from backend.server import app as flask_app, db as server_db

class TestMindFlowComponents(unittest.TestCase):
    
    def setUp(self):
        self.db = MindFlowDB()
        self.workspace = WorkspaceManager()
        # Ensure clean state for workspaces
        self.workspace.clean_workspace_folder()
        self.clean_profiles()

    def tearDown(self):
        self.workspace.clean_workspace_folder()
        self.clean_profiles()

    def clean_profiles(self):
        """Helper to clear any mock files from profiles."""
        for folder in [r"C:\MIND\Workspace_Profiles\Work", r"C:\MIND\Workspace_Profiles\Recharge"]:
            if os.path.exists(folder):
                for item in os.listdir(folder):
                    path = os.path.join(folder, item)
                    try:
                        if os.path.isdir(path):
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                    except Exception:
                        pass
        # Restore placeholders
        self.workspace.initialize_placeholders()

    def test_database_settings_handling(self):
        """Verify settings updates work correctly and types are safe."""
        original_settings = self.db.get_settings().copy()
        
        # Test schema-safe updating
        test_settings = {
            "work_duration_minutes": "30",  # String that should be converted to int
            "idle_timeout_seconds": 120,
            "work_keywords": ["VS Code", "GitHub", "   Antigravity   "],  # Mixed casing and spacing
            "recharge_keywords": ["Hades.exe", "YouTube"]
        }
        self.db.update_settings(test_settings)
        
        updated = self.db.get_settings()
        self.assertEqual(updated["work_duration_minutes"], 30)  # Verify int conversion
        self.assertEqual(updated["idle_timeout_seconds"], 120)
        self.assertIn("antigravity", updated["work_keywords"])  # Verify lowercase conversion & strip
        self.assertIn("hades.exe", updated["recharge_keywords"])
        
        # Restore
        self.db.update_settings(original_settings)

    def test_database_session_aggregation(self):
        """Verify dynamic calculation of today's work/recharge/rest seconds."""
        # Clean current session list for mock tests (we can temporarily mock sessions array)
        original_sessions = self.db.data["sessions"].copy()
        self.db.data["sessions"] = []
        
        t_now = datetime.now()
        
        # Log a work session of 100 seconds
        self.db.log_session("work", t_now, datetime(
            year=t_now.year, month=t_now.month, day=t_now.day,
            hour=t_now.hour, minute=t_now.minute, second=t_now.second
        ))
        # Ensure we test durations longer than 5 seconds
        import datetime as dt
        self.db.log_session("work", t_now, t_now + dt.timedelta(seconds=120), brain_dump="Finished parsing index.html changes", bypassed=True)
        self.db.log_session("recharge", t_now, t_now + dt.timedelta(seconds=80))
        
        sessions = self.db.get_sessions()
        work_sessions = [s for s in sessions if s["mode"] == "work"]
        recharge_sessions = [s for s in sessions if s["mode"] == "recharge"]
        
        self.assertEqual(len(work_sessions), 1)
        self.assertEqual(work_sessions[0]["duration"], 120)
        self.assertEqual(work_sessions[0]["brain_dump"], "Finished parsing index.html changes")
        self.assertTrue(work_sessions[0]["bypassed"])
        self.assertEqual(recharge_sessions[0]["duration"], 80)
        self.assertIsNone(recharge_sessions[0]["brain_dump"])
        self.assertFalse(recharge_sessions[0]["bypassed"])
        
        # Restore database sessions
        self.db.data["sessions"] = original_sessions
        self.db.save()

    def test_database_app_usage(self):
        """Verify logging and fetching application usage statistics in database."""
        original_app_usage = self.db.data.get("app_usage", []).copy()
        self.db.data["app_usage"] = []
        
        # Log app usage
        self.db.log_app_usage("code.exe", "index.html - MIND-FLOW", 15)
        self.db.log_app_usage("code.exe", "app.py - MIND-FLOW", 20)
        self.db.log_app_usage("chrome.exe", "Google Search", 45)
        
        usage = self.db.get_app_usage()
        
        # Check that we have exactly 2 unique processes logged
        self.assertEqual(len(usage), 2)
        
        # Verify aggregation on the same process on the same date
        code_entries = [u for u in usage if u["process"] == "code.exe"]
        chrome_entries = [u for u in usage if u["process"] == "chrome.exe"]
        
        self.assertEqual(len(code_entries), 1)
        self.assertEqual(code_entries[0]["duration"], 35)
        self.assertEqual(code_entries[0]["title"], "app.py - MIND-FLOW")  # Latest title
        
        self.assertEqual(len(chrome_entries), 1)
        self.assertEqual(chrome_entries[0]["duration"], 45)
        self.assertEqual(chrome_entries[0]["title"], "Google Search")
        
        # Restore original
        self.db.data["app_usage"] = original_app_usage
        self.db.save()

    def test_dual_mode_decision_logic(self):
        """Verify the state machine decision engine for processes vs title keywords."""
        
        # Mock settings values
        work_keywords = ["vs code", "code.exe", "github", "antigravity", "word", "excel"]
        recharge_keywords = ["steam.exe", "youtube", "hades.exe", "vlc"]
        idle_limit = 180
        
        # Decision engine simulator mimicking app.py logic
        def decide_mode(active_title, active_process, idle_sec):
            if idle_sec >= idle_limit:
                return "rest"
            
            is_work = any(matches_keyword(kw, active_process) or matches_keyword(kw, active_title) for kw in work_keywords)
            is_recharge = any(matches_keyword(kw, active_process) or matches_keyword(kw, active_title) for kw in recharge_keywords)
            
            if is_work:
                return "work"
            elif is_recharge:
                return "recharge"
            return "neutral"

        # Case 1: Browser active with Github work tab
        self.assertEqual(decide_mode("GitHub - pull requests", "chrome.exe", 10), "work")
        
        # Case 2: Browser active with Youtube chill tab
        self.assertEqual(decide_mode("Epic Lofi Playlist - YouTube", "msedge.exe", 10), "recharge")
        
        # Case 3: Dedicated game process running
        self.assertEqual(decide_mode("Game", "hades.exe", 10), "recharge")
        
        # Case 4: Dedicated code process running
        self.assertEqual(decide_mode("verify_tests.py - mind", "code.exe", 10), "work")
        
        # Case 5: Idle state limits
        self.assertEqual(decide_mode("verify_tests.py - mind", "code.exe", 200), "rest")
        
        # Case 6: Neutral process (e.g. calculator or explorer)
        self.assertEqual(decide_mode("Calculator", "calc.exe", 10), "neutral")
        
        # Case 7: Collision check - "word" keyword should NOT match "password tracker"
        self.assertEqual(decide_mode("password tracker", "chrome.exe", 10), "neutral")
        
        # Case 8: Collision check - "excel" keyword should NOT match "excellent recipe"
        self.assertEqual(decide_mode("excellent recipe", "chrome.exe", 10), "neutral")
        
        # Case 9: Word segmentation - "word" should match "my word doc"
        self.assertEqual(decide_mode("my word doc", "chrome.exe", 10), "work")

    def test_workspace_sweeping_and_collision_resolution(self):
        """Verify advanced workspace swapping and duplicate file collision handling."""
        self.workspace.clean_workspace_folder()
        self.clean_profiles()
        
        # 1. Create duplicate files in both Work Profile and Current_Workspace to force collision
        work_profile_file = os.path.join(r"C:\MIND\Workspace_Profiles\Work", "collision.txt")
        desktop_workspace_file = os.path.join(self.workspace.workspace_dir, "collision.txt")
        
        with open(work_profile_file, "w") as f:
            f.write("Profile Version")
            
        with open(desktop_workspace_file, "w") as f:
            f.write("Desktop Version (Modified)")
            
        # 2. Swap from work to recharge. This sweeps the desktop version back into the work profile,
        # resolving the collision by replacing the profile version with the modified desktop version.
        self.workspace.swap_workspace("work", "recharge")
        
        # Desktop file should be gone from active workspace
        self.assertFalse(os.path.exists(desktop_workspace_file))
        
        # Work profile file should now contain the "Desktop Version (Modified)"
        self.assertTrue(os.path.exists(work_profile_file))
        with open(work_profile_file, "r") as f:
            content = f.read()
        self.assertEqual(content, "Desktop Version (Modified)")

    def test_workspace_symlink_safety(self):
        """Verify that directory junctions and symbolic links are removed without traversing or deleting their target contents."""
        # Mock os.path.exists and islink
        with patch.object(self.workspace, 'is_link_or_junction', return_value=True) as mock_is_link, \
             patch('os.path.isdir', return_value=True) as mock_isdir, \
             patch('os.rmdir') as mock_rmdir, \
             patch('shutil.rmtree') as mock_rmtree, \
             patch('os.remove') as mock_remove:
             
            # Test safe_remove on a directory symlink/junction
            self.workspace.safe_remove("C:\\dummy\\junction_link")
            mock_is_link.assert_called_with("C:\\dummy\\junction_link")
            mock_isdir.assert_called_with("C:\\dummy\\junction_link")
            # Should call os.rmdir to remove the link, NOT shutil.rmtree
            mock_rmdir.assert_called_once_with("C:\\dummy\\junction_link")
            mock_rmtree.assert_not_called()
            mock_remove.assert_not_called()

        # Test safe_remove on a file symlink
        with patch.object(self.workspace, 'is_link_or_junction', return_value=True) as mock_is_link, \
             patch('os.path.isdir', return_value=False) as mock_isdir, \
             patch('os.rmdir') as mock_rmdir, \
             patch('shutil.rmtree') as mock_rmtree, \
             patch('os.remove') as mock_remove:
             
            self.workspace.safe_remove("C:\\dummy\\file_link")
            mock_is_link.assert_called_with("C:\\dummy\\file_link")
            mock_isdir.assert_called_with("C:\\dummy\\file_link")
            # Should call os.remove to remove the link, NOT shutil.rmtree
            mock_remove.assert_called_once_with("C:\\dummy\\file_link")
            mock_rmdir.assert_not_called()
            mock_rmtree.assert_not_called()

    def test_is_link_or_junction_attributes(self):
        """Verify is_link_or_junction detects reparse points using file attributes."""
        mock_stat = MagicMock()
        mock_stat.st_file_attributes = 1024  # Reparse point flag
        
        with patch('os.path.islink', return_value=False), \
             patch('os.lstat', return_value=mock_stat):
            self.assertTrue(self.workspace.is_link_or_junction("some_path"))
            
        mock_stat.st_file_attributes = 0  # No reparse point flag
        with patch('os.path.islink', return_value=False), \
             patch('os.lstat', return_value=mock_stat):
            self.assertFalse(self.workspace.is_link_or_junction("some_path"))

    def test_ctypes_sensors_safeguard(self):
        """Verify the DLL sensor hooks return safe, correct types."""
        title = get_active_window_title()
        self.assertIsInstance(title, str)
        
        process = get_active_process_name()
        self.assertIsInstance(process, str)
        idle = get_idle_seconds()
        self.assertIsInstance(idle, (int, float))
        self.assertGreaterEqual(idle, 0)

    def test_rigorous_edge_cases(self):
        """Perform rigorous edge-case testing on word segmentation, filters, and thread safety."""
        # 1. Prohibited Browser Keyword Filtering
        original_settings = self.db.get_settings().copy()
        try:
            self.db.update_settings({
                "work_keywords": ["chrome.exe", "firefox", "google docs", "antigravity"],
                "recharge_keywords": ["youtube", "msedge", "steam.exe"]
            })
            settings = self.db.get_settings()
            
            # Prohibited browser terms should be filtered out
            self.assertNotIn("chrome.exe", settings["work_keywords"])
            self.assertNotIn("firefox", settings["work_keywords"])
            self.assertNotIn("msedge", settings["recharge_keywords"])
            
            # Allowed terms should be retained
            self.assertIn("google docs", settings["work_keywords"])
            self.assertIn("antigravity", settings["work_keywords"])
            self.assertIn("youtube", settings["recharge_keywords"])
        finally:
            self.db.update_settings(original_settings)

        # 2. Word Segmentation Boundary Checks
        # Alphanumeric keywords
        self.assertTrue(matches_keyword("word", "my word document"))
        self.assertFalse(matches_keyword("word", "password protection"))
        
        # Keywords with special characters (dot, space)
        self.assertTrue(matches_keyword("code.exe", "code.exe"))
        self.assertTrue(matches_keyword("code.exe", "Active process: code.exe"))
        self.assertFalse(matches_keyword("code.exe", "mycode.exe"))
        self.assertFalse(matches_keyword("code.exe", "code.exe2"))
        
        self.assertTrue(matches_keyword("vs code", "vs code editor"))
        self.assertFalse(matches_keyword("vs code", "devs code"))
        
        # Case Insensitivity
        self.assertTrue(matches_keyword("VS CODE", "vs code"))
        self.assertTrue(matches_keyword("vs code", "VS CODE"))

        # 3. Database Thread-Safety Lock Test (Concurrent writes/reads)
        import threading
        
        exceptions = []
        def worker():
            try:
                for _ in range(15):
                    self.db.save()
                    self.db.load()
            except Exception as e:
                exceptions.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No exceptions should have occurred during concurrent load/saves
        self.assertEqual(len(exceptions), 0, f"Thread-safety locks failed: {exceptions}")

    def test_adaptive_times(self):
        """Verify dynamic calculations for work sprint and rest recovery modifiers, ceilings, and floors."""
        original_settings = self.db.get_settings().copy()
        original_sessions = self.db.data["sessions"].copy()
        original_reflections = self.db.data["reflections"].copy()
        
        try:
            self.db.update_settings({"work_duration_minutes": 45})
            
            # Scenario A: Default (no reflections, no bypasses)
            self.db.data["sessions"] = []
            self.db.data["reflections"] = []
            res = self.db.get_adaptive_times()
            self.assertEqual(res["work_minutes"], 45)
            self.assertEqual(res["rest_seconds"], 20)
            self.assertEqual(res["reason"], "Default")
            
            # Scenario B: High Energy (5) + Low Friction (1) reflection -> Flow extension
            self.db.add_reflection(5, 1, "Feeling super in the flow")
            res = self.db.get_adaptive_times()
            # ref_work_mod = (5-3)*5 + (3-1)*5 = 20, capped at 15
            # total work: 45 + 15 = 60 minutes
            self.assertEqual(res["work_minutes"], 60)
            self.assertEqual(res["rest_seconds"], 20)
            self.assertIn("Flow (+15m)", res["reason"])
            
            # Scenario C: Flow reflection + 1 bypass penalty today
            from datetime import datetime, timedelta
            self.db.log_session("work", datetime.now() - timedelta(minutes=10), datetime.now(), bypassed=True)
            res = self.db.get_adaptive_times()
            # work: 45 + 15 (flow) - 5 (bypass) = 55 mins
            # rest: 20 + 10 (bypass) = 30 seconds
            self.assertEqual(res["work_minutes"], 55)
            self.assertEqual(res["rest_seconds"], 30)
            self.assertIn("Flow (+15m)", res["reason"])
            self.assertIn("Bypasses (-5m)", res["reason"])
            self.assertIn("Rest Deficit (+10s)", res["reason"])
            
            # Scenario D: High fatigue reflection (energy 1, friction 5) + 3 bypasses -> Severe constraint
            self.db.data["reflections"] = []
            self.db.add_reflection(1, 5, "Exhausted and stuck")
            # Log two more bypasses to make it 3 total
            self.db.log_session("work", datetime.now() - timedelta(minutes=10), datetime.now(), bypassed=True)
            self.db.log_session("work", datetime.now() - timedelta(minutes=10), datetime.now(), bypassed=True)
            res = self.db.get_adaptive_times()
            
            # fatigue modifier: -((3-1)*5 + (5-3)*5) = -20, capped at -15
            # bypass modifier: 3 * -5 = -15
            # Total modifier: -30
            # Target work minutes: 45 - 30 = 15 minutes
            self.assertEqual(res["work_minutes"], 15)
            
            # rest fatigue addition: +10 seconds
            # rest bypass deficit: 3 * 10 = 30 seconds
            # Total rest: 20 + 10 + 30 = 60 seconds
            self.assertEqual(res["rest_seconds"], 60)
            self.assertIn("Fatigue (-15m)", res["reason"])
            self.assertIn("Bypasses (-15m)", res["reason"])
            self.assertIn("Rest Alert (+10s)", res["reason"])
            self.assertIn("Rest Deficit (+30s)", res["reason"])
            
            # Scenario E: Verify Floor Safety bounds (Work must not fall below 10 mins)
            self.db.update_settings({"work_duration_minutes": 15})
            res = self.db.get_adaptive_times()
            # 15 - 30 = -15, should floor to 10 minutes
            self.assertEqual(res["work_minutes"], 10)
            
            # Scenario F: Verify Disable Autopilot Toggle
            self.db.update_settings({"adaptive_timers_enabled": False, "work_duration_minutes": 45})
            res = self.db.get_adaptive_times()
            self.assertEqual(res["work_minutes"], 45)
            self.assertEqual(res["rest_seconds"], 20)
            self.assertEqual(res["reason"], "Autopilot Off")
            
        finally:
            self.db.update_settings(original_settings)
            self.db.data["sessions"] = original_sessions
            self.db.data["reflections"] = original_reflections
            self.db.save()

class TestMindFlowAPI(unittest.TestCase):
    def setUp(self):
        self.client = flask_app.test_client()
        self.db = server_db
        # Backup shared state
        self.original_state = shared_state.copy()
        
    def tearDown(self):
        # Restore shared state
        for k, v in self.original_state.items():
            shared_state[k] = v

    def test_get_status(self):
        response = self.client.get('/api/status')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("current_mode", data)
        self.assertIn("active_window_title", data)
        self.assertIn("active_process_name", data)
        self.assertIn("elapsed_seconds", data)
        self.assertIn("work_limit_seconds", data)
        self.assertIn("adaptive_work_limit_seconds", data)
        self.assertIn("adaptive_rest_limit_seconds", data)
        self.assertIn("adaptive_reason", data)
        self.assertIn("idle_seconds", data)
        self.assertIn("tracking_active", data)
        self.assertIn("current_energy", data)
        self.assertIn("today_work_seconds", data)
        self.assertIn("today_recharge_seconds", data)
        self.assertIn("today_rest_seconds", data)
        self.assertIn("today_bypasses", data)
        self.assertIn("companion_message", data)

    def test_require_local_origin(self):
        # 1. No Origin/Referer headers should be allowed
        response = self.client.post('/api/status/toggle', json={"enable": True})
        self.assertEqual(response.status_code, 200)

        # 2. Valid Origin header should be allowed
        response = self.client.post('/api/status/toggle', json={"enable": True}, headers={"Origin": "http://localhost:5000"})
        self.assertEqual(response.status_code, 200)
        
        response = self.client.post('/api/status/toggle', json={"enable": True}, headers={"Origin": "http://127.0.0.1:5000"})
        self.assertEqual(response.status_code, 200)

        # 3. Invalid Origin header should be blocked
        response = self.client.post('/api/status/toggle', json={"enable": True}, headers={"Origin": "http://localhost.attacker.com"})
        self.assertEqual(response.status_code, 403)
        
        response = self.client.post('/api/status/toggle', json={"enable": True}, headers={"Origin": "http://attacker.com?origin=localhost"})
        self.assertEqual(response.status_code, 403)

        # 4. Valid Referer header (when no Origin) should be allowed
        response = self.client.post('/api/status/toggle', json={"enable": True}, headers={"Referer": "http://localhost:5000/dashboard"})
        self.assertEqual(response.status_code, 200)

        # 5. Invalid Referer header (when no Origin) should be blocked
        response = self.client.post('/api/status/toggle', json={"enable": True}, headers={"Referer": "http://attacker.com/localhost"})
        self.assertEqual(response.status_code, 403)

    def test_toggle_tracking(self):
        # Test toggling off
        response = self.client.post('/api/status/toggle', json={"enable": False})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["tracking_active"])
        self.assertFalse(shared_state["tracking_active"])

        # Test toggling back on (no body sends toggle)
        response = self.client.post('/api/status/toggle')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["tracking_active"])
        self.assertTrue(shared_state["tracking_active"])

    def test_trigger_manual_lockout(self):
        response = self.client.post('/api/status/lockout')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(shared_state["manual_lockout_requested"])

    def test_manage_settings(self):
        # Get settings
        response = self.client.get('/api/settings')
        self.assertEqual(response.status_code, 200)
        settings = response.get_json()
        self.assertIn("work_duration_minutes", settings)

        # Post settings
        orig = self.db.get_settings().copy()
        try:
            response = self.client.post('/api/settings', json={"work_duration_minutes": 55})
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["settings"]["work_duration_minutes"], 55)
            self.assertEqual(self.db.get_settings()["work_duration_minutes"], 55)
        finally:
            self.db.update_settings(orig)

    def test_manage_reflections(self):
        # Get reflections
        response = self.client.get('/api/reflections')
        self.assertEqual(response.status_code, 200)
        reflections = response.get_json()
        self.assertIsInstance(reflections, list)

        # Post reflection
        original_reflections = self.db.data["reflections"].copy()
        try:
            response = self.client.post('/api/reflections', json={
                "energy_level": 4,
                "friction_level": 2,
                "summary": "Testing API Reflection"
            })
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["reflection"]["energy_level"], 4)
            self.assertEqual(data["reflection"]["friction_level"], 2)
            self.assertEqual(data["reflection"]["summary"], "Testing API Reflection")
            
            # Missing param
            response2 = self.client.post('/api/reflections', json={
                "energy_level": 4
            })
            self.assertEqual(response2.status_code, 400)
        finally:
            self.db.data["reflections"] = original_reflections
            self.db.save()

    def test_get_analytics(self):
        response = self.client.get('/api/analytics')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("reflections", data)
        self.assertIn("weekday_summary", data)
        self.assertIn("recommendations", data)
        self.assertIn("insights", data)
        self.assertIn("app_usage", data)
        self.assertIsInstance(data["app_usage"], list)

    @patch('os._exit')
    def test_shutdown_app(self, mock_exit):
        # Patch swap_workspace to avoid actually moving user's desktop files during test
        with patch('backend.workspace.WorkspaceManager.swap_workspace') as mock_swap:
            response = self.client.post('/api/shutdown')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["status"], "shutdown_initiated")
            mock_swap.assert_called_once()
            
            # Wait brief moment for the terminate thread to call os._exit
            import time
            for _ in range(10):
                if mock_exit.called:
                    break
                time.sleep(0.1)
            mock_exit.assert_called_with(0)

    def test_host_header_validation(self):
        # 1. Valid Host headers should be allowed
        response = self.client.get('/api/status', headers={"Host": "localhost:5000"})
        self.assertEqual(response.status_code, 200)
        
        response = self.client.get('/api/status', headers={"Host": "127.0.0.1:5000"})
        self.assertEqual(response.status_code, 200)

        # 2. Invalid Host headers should be blocked (DNS rebinding simulation)
        response = self.client.get('/api/status', headers={"Host": "attacker.com"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("Invalid Host header", response.get_json()["error"])
        
        response = self.client.get('/api/status', headers={"Host": "localhost.attacker.com:5000"})
        self.assertEqual(response.status_code, 403)

        # 3. Request from non-local IP with missing Origin/Referer should be blocked
        response = self.client.post('/api/status/toggle', json={"enable": True}, environ_base={'REMOTE_ADDR': '192.168.1.100'})
        self.assertEqual(response.status_code, 403)
        
        # 4. Request from local IP with missing Origin/Referer should be allowed
        response = self.client.post('/api/status/toggle', json={"enable": True}, environ_base={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(response.status_code, 200)

class TestAppWindowLaunch(unittest.TestCase):
    @patch('os.path.exists')
    @patch('subprocess.Popen')
    def test_launch_app_window_chrome(self, mock_popen, mock_exists):
        # Simulate Chrome existing, Edge not existing
        def exists_side_effect(path):
            return "chrome.exe" in path.lower()
        mock_exists.side_effect = exists_side_effect
        
        result = launch_app_window("http://localhost:5000")
        self.assertTrue(result)
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertIn("chrome.exe", args[0].lower())
        self.assertIn("--app=http://localhost:5000", args[1])

    @patch('os.path.exists')
    @patch('subprocess.Popen')
    def test_launch_app_window_edge(self, mock_popen, mock_exists):
        # Simulate Chrome NOT existing, Edge existing
        def exists_side_effect(path):
            return "msedge.exe" in path.lower()
        mock_exists.side_effect = exists_side_effect
        
        result = launch_app_window("http://localhost:5000")
        self.assertTrue(result)
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertIn("msedge.exe", args[0].lower())
        self.assertIn("--app=http://localhost:5000", args[1])

    @patch('os.path.exists')
    @patch('webbrowser.open')
    def test_launch_app_window_fallback(self, mock_web_open, mock_exists):
        # Simulate neither Chrome nor Edge existing
        mock_exists.return_value = False
        
        result = launch_app_window("http://localhost:5000")
        self.assertFalse(result)
        mock_web_open.assert_called_once_with("http://localhost:5000")

class TestLockoutOverlay(unittest.TestCase):
    @patch('app.tk.Tk')
    @patch('app.tk.Frame')
    @patch('app.tk.Label')
    @patch('app.tk.Text')
    @patch('app.tk.Button')
    @patch('app.tk.Canvas')
    @patch('app.winsound.Beep')
    def test_trigger_lockout_overlay_submit(self, mock_beep, mock_canvas, mock_button, mock_text, mock_label, mock_frame, mock_tk):
        mock_root = MagicMock()
        mock_root.winfo_screenwidth.return_value = 1920
        mock_root.winfo_screenheight.return_value = 1080
        mock_tk.return_value = mock_root

        mock_text_inst = MagicMock()
        mock_text_inst.get.return_value = "Test Brain Dump Content"
        mock_text.return_value = mock_text_inst

        bindings = {}
        def mock_bind(event, callback):
            bindings[event] = callback
        mock_root.bind.side_effect = mock_bind

        button_cmd = None
        def mock_btn_init(*args, **kwargs):
            nonlocal button_cmd
            button_cmd = kwargs.get("command")
            return MagicMock()
        mock_button.side_effect = mock_btn_init

        after_callbacks = []
        def mock_after(ms, func, *args):
            after_callbacks.append(func)
        mock_root.after.side_effect = mock_after

        # Simulate normal mainloop that triggers the button command
        def simulate_mainloop():
            if button_cmd:
                button_cmd()
            # Run collected after callbacks
            while after_callbacks:
                cb = after_callbacks.pop(0)
                cb()
        mock_root.mainloop.side_effect = simulate_mainloop

        dump, completed = trigger_lockout_overlay(1)
        self.assertEqual(dump, "Test Brain Dump Content")
        self.assertTrue(completed)

    @patch('app.tk.Tk')
    @patch('app.tk.Frame')
    @patch('app.tk.Label')
    @patch('app.tk.Text')
    @patch('app.tk.Button')
    @patch('app.tk.Canvas')
    @patch('app.winsound.Beep')
    def test_trigger_lockout_overlay_escape(self, mock_beep, mock_canvas, mock_button, mock_text, mock_label, mock_frame, mock_tk):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root

        bindings = {}
        def mock_bind(event, callback):
            bindings[event] = callback
        mock_root.bind.side_effect = mock_bind

        def simulate_mainloop():
            # Trigger Escape key press
            if "<Escape>" in bindings:
                bindings["<Escape>"](None)
        mock_root.mainloop.side_effect = simulate_mainloop

        dump, completed = trigger_lockout_overlay(10)
        self.assertEqual(dump, "")
        self.assertFalse(completed)

class TestMainStateMachine(unittest.TestCase):
    def setUp(self):
        self.original_state = shared_state.copy()
        
    def tearDown(self):
        for k, v in self.original_state.items():
            shared_state[k] = v

    @patch('app.time.sleep')
    @patch('app.get_active_window_title')
    @patch('app.get_active_process_name')
    @patch('app.get_idle_seconds')
    @patch('app.WorkspaceManager')
    @patch('app.db')
    def test_state_machine_tracking_inactive(self, mock_db, mock_ws_class, mock_idle, mock_proc, mock_title, mock_sleep):
        # Mock workspace instance
        mock_ws = MagicMock()
        mock_ws_class.return_value = mock_ws
        
        # Setup settings mocks
        mock_db.get_settings.return_value = {
            "work_keywords": ["code.exe"],
            "recharge_keywords": ["game.exe"],
            "idle_timeout_seconds": 180
        }
        mock_db.get_adaptive_times.return_value = {
            "work_minutes": 45,
            "rest_seconds": 20,
            "reason": "Default"
        }
        mock_db.get_reflections.return_value = []
        
        # Iteration 1: tracking is active, active window is work
        mock_title.return_value = "VS Code"
        mock_proc.return_value = "code.exe"
        mock_idle.return_value = 5.0
        
        shared_state["tracking_active"] = True
        shared_state["current_mode"] = "neutral"
        
        # Custom sleep side effect to change tracking_active to False on the second iteration
        sleep_count = 0
        def sleep_side_effect(secs):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count == 1:
                # Keep tracking active for the first iteration to transition to work
                pass
            elif sleep_count == 2:
                # Disable tracking for the second iteration to trigger sweep back
                shared_state["tracking_active"] = False
            elif sleep_count >= 3:
                # Exit state machine loop
                raise KeyboardInterrupt
        mock_sleep.side_effect = sleep_side_effect
        
        from app import main_state_machine
        with self.assertRaises(KeyboardInterrupt):
            main_state_machine()
            
        # Verify that because tracking was inactive and current_mode was "work",
        # it transitioned to neutral and swept the workspace.
        self.assertEqual(shared_state["current_mode"], "neutral")
        mock_ws.swap_workspace.assert_called_with("work", "neutral")
        mock_db.log_session.assert_called()

    @patch('app.time.sleep')
    @patch('app.get_active_window_title')
    @patch('app.get_active_process_name')
    @patch('app.get_idle_seconds')
    @patch('app.WorkspaceManager')
    @patch('app.db')
    def test_state_machine_work_transition(self, mock_db, mock_ws_class, mock_idle, mock_proc, mock_title, mock_sleep):
        mock_ws = MagicMock()
        mock_ws_class.return_value = mock_ws
        
        # Setup settings mocks
        mock_db.get_settings.return_value = {
            "work_keywords": ["code.exe"],
            "recharge_keywords": ["game.exe"],
            "idle_timeout_seconds": 180
        }
        mock_db.get_adaptive_times.return_value = {
            "work_minutes": 45,
            "rest_seconds": 20,
            "reason": "Default"
        }
        mock_db.get_reflections.return_value = []
        
        # State: work window is active
        mock_title.return_value = "VS Code"
        mock_proc.return_value = "code.exe"
        mock_idle.return_value = 5.0
        
        shared_state["tracking_active"] = True
        shared_state["current_mode"] = "neutral"
        
        # Raise KeyboardInterrupt on second sleep to allow one iteration to process
        sleep_count = 0
        def sleep_side_effect(secs):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count >= 2:
                raise KeyboardInterrupt
        mock_sleep.side_effect = sleep_side_effect
        
        from app import main_state_machine
        with self.assertRaises(KeyboardInterrupt):
            main_state_machine()
            
        # Verify transition to work occurred
        self.assertEqual(shared_state["current_mode"], "work")
        mock_ws.swap_workspace.assert_called_with("neutral", "work")

    @patch('app.time.sleep')
    @patch('app.get_active_window_title')
    @patch('app.get_active_process_name')
    @patch('app.get_idle_seconds')
    @patch('app.WorkspaceManager')
    @patch('app.db')
    @patch('app.trigger_lockout_overlay')
    def test_state_machine_manual_lockout(self, mock_overlay, mock_db, mock_ws_class, mock_idle, mock_proc, mock_title, mock_sleep):
        mock_ws = MagicMock()
        mock_ws_class.return_value = mock_ws
        
        mock_db.get_settings.return_value = {
            "work_keywords": ["code.exe"],
            "recharge_keywords": ["game.exe"],
            "idle_timeout_seconds": 180
        }
        mock_db.get_adaptive_times.return_value = {
            "work_minutes": 45,
            "rest_seconds": 20,
            "reason": "Default"
        }
        mock_db.get_reflections.return_value = []
        
        # Request manual lockout
        shared_state["tracking_active"] = True
        shared_state["current_mode"] = "work"
        shared_state["manual_lockout_requested"] = True
        
        mock_overlay.return_value = ("Manual Dump", True)
        
        sleep_count = 0
        def sleep_side_effect(secs):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count >= 2:
                raise KeyboardInterrupt
        mock_sleep.side_effect = sleep_side_effect
        
        from app import main_state_machine
        with self.assertRaises(KeyboardInterrupt):
            main_state_machine()
            
        # Verify lockout was triggered and logged
        mock_overlay.assert_called_with(20)
        # Should log previous session (work) and the rest session
        self.assertEqual(mock_db.log_session.call_count, 2)
        # Verify second call logged rest with manual dump and completed
        calls = mock_db.log_session.call_args_list
        rest_call = calls[1]
        self.assertEqual(rest_call[0][0], "rest")
        self.assertEqual(rest_call[1]["brain_dump"], "Manual Dump")
        self.assertEqual(rest_call[1]["bypassed"], False)

if __name__ == "__main__":
    unittest.main()
