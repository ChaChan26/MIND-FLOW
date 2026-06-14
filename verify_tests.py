import os
os.environ["MINDFLOW_DB_FILE"] = ":memory:"
import shutil
import unittest
import sqlite3
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

from backend.database import MindFlowDB
import time
import subprocess
import webbrowser
from app import get_active_window_title, get_active_process_name, get_idle_seconds, matches_keyword, shared_state, launch_app_window
from backend.server import app as flask_app, db as server_db

def clear_db(db):
    with db.connection() as conn:
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM reflections")
        conn.execute("DELETE FROM app_usage")
        conn.execute("DELETE FROM hydration")
        conn.execute("DELETE FROM steps")
        conn.execute("DELETE FROM sleep")
        conn.execute("DELETE FROM settings")
        conn.execute("DELETE FROM metadata")
    db._init_db()

class TestMindFlowComponents(unittest.TestCase):
    
    def setUp(self):
        self._master_conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
        self.db = MindFlowDB()
        clear_db(self.db)

    def tearDown(self):
        self.db.close()
        self._master_conn.close()

    def test_database_settings_handling(self):
        """Verify settings updates work correctly and types are safe."""
        original_settings = self.db.get_settings().copy()
        
        # Test schema-safe updating
        test_settings = {
            "work_duration_minutes": "30",  # String that should be converted to int
            "idle_timeout_seconds": 120,
            "rest_duration_seconds": "25",  # String that should be converted to int
            "eye_care_mode": True,
            "work_keywords": ["VS Code", "GitHub", "   Antigravity   "],  # Mixed casing and spacing
            "recharge_keywords": ["Hades.exe", "YouTube"]
        }
        self.db.update_settings(test_settings)
        
        updated = self.db.get_settings()
        self.assertEqual(updated["work_duration_minutes"], 30)  # Verify int conversion
        self.assertEqual(updated["idle_timeout_seconds"], 120)
        self.assertEqual(updated["rest_duration_seconds"], 25)  # Verify int conversion
        self.assertTrue(updated["eye_care_mode"])
        self.assertIn("antigravity", updated["work_keywords"])  # Verify lowercase conversion & strip
        self.assertIn("hades.exe", updated["recharge_keywords"])
        
        # Test type validation safety (invalid integer ignored)
        self.db.update_settings({"work_duration_minutes": "invalid"})
        self.assertEqual(self.db.get_settings()["work_duration_minutes"], 30)
        
        # Test range clamping bounds (prevent lockout / zero errors)
        self.db.update_settings({"work_duration_minutes": 2, "idle_timeout_seconds": 5, "rest_duration_seconds": 1})
        clamped = self.db.get_settings()
        self.assertEqual(clamped["work_duration_minutes"], 10)  # Min work limit
        self.assertEqual(clamped["idle_timeout_seconds"], 10)  # Min idle limit
        self.assertEqual(clamped["rest_duration_seconds"], 5)   # Min rest limit
        
        # Test string boolean parsing
        self.db.update_settings({"eye_care_mode": "false", "adaptive_timers_enabled": "true"})
        self.assertFalse(self.db.get_settings()["eye_care_mode"])
        self.assertTrue(self.db.get_settings()["adaptive_timers_enabled"])

        # Test hydration settings updates
        self.db.update_settings({
            "hydration_target": 2000,
            "hydration_unit": "ml",
            "hydration_increment": 250
        })
        hyd_settings = self.db.get_settings()
        self.assertEqual(hyd_settings["hydration_target"], 2000)
        self.assertEqual(hyd_settings["hydration_unit"], "ml")
        self.assertEqual(hyd_settings["hydration_increment"], 250)

        # Test invalid values / validation clamps
        self.db.update_settings({
            "hydration_target": -5,          # Should clamp to 1
            "hydration_unit": "gallons",      # Should ignore (keep ml)
            "hydration_increment": 10000      # Should clamp to 5000
        })
        clamped_hyd = self.db.get_settings()
        self.assertEqual(clamped_hyd["hydration_target"], 1)
        self.assertEqual(clamped_hyd["hydration_unit"], "ml")
        self.assertEqual(clamped_hyd["hydration_increment"], 5000)

        # Restore
        self.db.update_settings(original_settings)

    def test_database_session_aggregation(self):
        """Verify dynamic calculation of today's work/recharge/rest seconds."""
        with self.db.connection() as conn:
            conn.execute("DELETE FROM sessions")
        
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

    def test_database_app_usage(self):
        """Verify logging and fetching application usage statistics in database."""
        with self.db.connection() as conn:
            conn.execute("DELETE FROM app_usage")
        
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
        self.assertIn("titles", code_entries[0])
        self.assertEqual(code_entries[0]["titles"]["index.html - MIND-FLOW"], 15)
        self.assertEqual(code_entries[0]["titles"]["app.py - MIND-FLOW"], 20)
        
        self.assertEqual(len(chrome_entries), 1)
        self.assertEqual(chrome_entries[0]["duration"], 45)
        self.assertEqual(chrome_entries[0]["title"], "Google Search")
        self.assertIn("titles", chrome_entries[0])
        self.assertEqual(chrome_entries[0]["titles"]["Google Search"], 45)

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
        # 1. Prohibited Browser Keyword Filtering (Now allowed, but handled at classification level)
        original_settings = self.db.get_settings().copy()
        try:
            self.db.update_settings({
                "work_keywords": ["chrome.exe", "firefox", "google docs", "antigravity"],
                "recharge_keywords": ["youtube", "msedge", "steam.exe"]
            })
            settings = self.db.get_settings()
            
            # Browser terms should be retained in settings now
            self.assertIn("chrome.exe", settings["work_keywords"])
            self.assertIn("firefox", settings["work_keywords"])
            self.assertIn("msedge", settings["recharge_keywords"])
            
            # Allowed terms should be retained
            self.assertIn("google docs", settings["work_keywords"])
            self.assertIn("antigravity", settings["work_keywords"])
            self.assertIn("youtube", settings["recharge_keywords"])
            
            # Verify classification logic for browsers vs titles
            from backend.database import is_browser_process, matches_any_keyword
            self.assertTrue(is_browser_process("chrome.exe"))
            self.assertTrue(is_browser_process("firefox"))
            
            def decide_mode_v2(active_title, active_process):
                if is_browser_process(active_process):
                    is_work = matches_any_keyword(settings["work_keywords"], active_title)
                    is_recharge = matches_any_keyword(settings["recharge_keywords"], active_title)
                else:
                    is_work = matches_any_keyword(settings["work_keywords"], active_process) or matches_any_keyword(settings["work_keywords"], active_title)
                    is_recharge = matches_any_keyword(settings["recharge_keywords"], active_process) or matches_any_keyword(settings["recharge_keywords"], active_title)
                if is_work: return "work"
                if is_recharge: return "recharge"
                return "neutral"
                
            self.assertEqual(decide_mode_v2("YouTube Video", "chrome.exe"), "recharge")
            self.assertEqual(decide_mode_v2("Random Page", "chrome.exe"), "neutral")
            self.assertEqual(decide_mode_v2("Google Docs - Editor", "chrome.exe"), "work")
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
        self.assertTrue(matches_keyword("vs code", "vs code"))

        # Keywords starting with non-alphanumeric characters (like file extensions)
        self.assertTrue(matches_keyword(".py", "app.py"))
        self.assertTrue(matches_keyword(".exe", "chrome.exe"))
        self.assertFalse(matches_keyword(".py", "app.pyc"))
        
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

    @patch('backend.database.datetime')
    def test_adaptive_times(self, mock_datetime):
        """Verify dynamic calculations for work sprint and rest recovery modifiers, ceilings, and floors."""
        import datetime as dt
        t_now = dt.datetime(2026, 6, 1, 9, 0, 0)
        mock_datetime.now.return_value = t_now
        mock_datetime.fromisoformat.side_effect = lambda x: dt.datetime.fromisoformat(x)
        mock_datetime.today.return_value = t_now
        original_settings = self.db.get_settings().copy()
        
        try:
            self.db.update_settings({"work_duration_minutes": 45, "adaptive_timers_enabled": True})
            
            # Scenario A: Default (no reflections, no bypasses)
            with self.db.connection() as conn:
                conn.execute("DELETE FROM sessions")
                conn.execute("DELETE FROM reflections")
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
            from datetime import timedelta
            self.db.log_session("work", t_now - timedelta(minutes=10), t_now, bypassed=True)
            res = self.db.get_adaptive_times()
            # work: 45 + 15 (flow) - 5 (bypass) = 55 mins
            # rest: 20 + 10 (bypass) = 30 seconds
            self.assertEqual(res["work_minutes"], 55)
            self.assertEqual(res["rest_seconds"], 30)
            self.assertIn("Flow (+15m)", res["reason"])
            self.assertIn("Bypasses (-5m)", res["reason"])
            self.assertIn("Rest Deficit (+10s)", res["reason"])
            
            # Scenario D: High fatigue reflection (energy 1, friction 5) + 3 bypasses -> Severe constraint
            with self.db.connection() as conn:
                conn.execute("DELETE FROM reflections")
            self.db.add_reflection(1, 5, "Exhausted and stuck")
            # Log two more bypasses to make it 3 total
            self.db.log_session("work", t_now - timedelta(minutes=10), t_now, bypassed=True)
            self.db.log_session("work", t_now - timedelta(minutes=10), t_now, bypassed=True)
            res = self.db.get_adaptive_times()
            
            # fatigue modifier: -((3-1)*5 + (5-3)*5) = -20, capped at -15
            # bypass modifier: 3 * -5 = -15, capped at -10 now
            # Total modifier: -25
            # Target work minutes: 45 - 25 = 20 minutes
            self.assertEqual(res["work_minutes"], 20)
            
            # rest fatigue addition: +10 seconds
            # rest bypass deficit: 3 * 10 = 30 seconds, capped at 20 now
            # friction rest addition: +24 seconds (avg friction 5.0 -> +24s)
            # Total rest: 20 + 10 + 20 + 24 = 74 seconds
            self.assertEqual(res["rest_seconds"], 74)
            self.assertIn("Fatigue (-15m)", res["reason"])
            self.assertIn("Bypasses (-10m)", res["reason"])
            self.assertIn("Rest Alert (+10s)", res["reason"])
            self.assertIn("Rest Deficit (+20s)", res["reason"])
            self.assertIn("Friction Deficit (+24s)", res["reason"])
            
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

    def test_circadian_forecast_generation(self):
        """Verify the database correctly calculates and interpolates the circadian forecast."""
        # Clean reflections for predictable environment
        with self.db.connection() as conn:
            conn.execute("DELETE FROM reflections")
        
        # Scenario A: Default Curve (no reflections)
        forecast = self.db.get_circadian_forecast()
        # Predicted energy should match default curve at current hour
        now = datetime.now()
        from backend.database import DEFAULT_CIRCADIAN_CURVE
        expected_current = DEFAULT_CIRCADIAN_CURVE[now.hour]
        self.assertTrue(1.0 <= forecast["current_predicted_energy"] <= 5.0)
        self.assertEqual(len(forecast["forecast_curve"]), 24)
        
        # Scenario B: Blend with reflections
        from datetime import timedelta
        t_now = datetime.now()
        # Add 3 reflections today in current hour
        self.db.add_reflection(2, 2, "Tired reflection")
        self.db.add_reflection(2, 2, "Still tired")
        self.db.add_reflection(2, 2, "Very tired")
        
        forecast_blended = self.db.get_circadian_forecast()
        # The current hour prediction should be shifted downwards towards 2.0
        self.assertLessEqual(forecast_blended["forecast_curve"][t_now.hour]["energy"], 3.2)


    @patch('backend.database.datetime')
    def test_circadian_schedule_adjustment(self, mock_datetime):
        """Verify the autopilot adjust sprint/rest duration based on forecasted slump."""
        import datetime as dt
        t_now = dt.datetime(2026, 6, 1, 9, 0, 0)
        mock_datetime.now.return_value = t_now
        mock_datetime.fromisoformat.side_effect = lambda x: dt.datetime.fromisoformat(x)
        mock_datetime.today.return_value = t_now
        original_settings = self.db.get_settings().copy()
        try:
            self.db.update_settings({
                "work_duration_minutes": 45,
                "rest_duration_seconds": 20,
                "circadian_forecast_enabled": True,
                "circadian_forecast_sensitivity": "medium"
            })
            
            # Inject peak reflections now and in 30 mins, and a crash reflection in 60 mins
            # to trigger a clear, robust impending drop forecast at any time of day
            from datetime import timedelta
            now_dt = t_now
            time_0 = now_dt - timedelta(days=1)
            time_1 = now_dt + timedelta(minutes=30) - timedelta(days=1)
            time_2 = now_dt + timedelta(minutes=60) - timedelta(days=1)
            
            with self.db.connection() as conn:
                conn.execute("DELETE FROM reflections")
                conn.execute("""
                    INSERT INTO reflections (timestamp, energy_level, friction_level, summary, mood)
                    VALUES (?, ?, ?, ?, ?)
                """, (time_0.isoformat(), 5, 1, "Current peak reflection", "Focused"))
                conn.execute("""
                    INSERT INTO reflections (timestamp, energy_level, friction_level, summary, mood)
                    VALUES (?, ?, ?, ?, ?)
                """, (time_1.isoformat(), 5, 1, "Current peak reflection 2", "Focused"))
                conn.execute("""
                    INSERT INTO reflections (timestamp, energy_level, friction_level, summary, mood)
                    VALUES (?, ?, ?, ?, ?)
                """, (time_2.isoformat(), 1, 5, "Imminent crash reflection", "Exhausted"))
            
            forecast = self.db.get_circadian_forecast()
            self.assertTrue(forecast["impending_drop"])
            
            # Verify adaptive times adjusts sprint pacing
            res = self.db.get_adaptive_times()
            # Medium sensitivity should subtract 10m from work and add 15s to rest
            self.assertEqual(res["work_minutes"], 35) # 45 - 10
            self.assertEqual(res["rest_seconds"], 35) # 20 + 15
            self.assertIn("Slump Forecast (-10m)", res["reason"])
            self.assertIn("Rest Pacing (+15s)", res["reason"])
            
            # Verify disabling circadian forecast turns off the adjustment
            self.db.update_settings({"circadian_forecast_enabled": False})
            res_disabled = self.db.get_adaptive_times()
            self.assertEqual(res_disabled["work_minutes"], 45)
            self.assertEqual(res_disabled["rest_seconds"], 20)
            self.assertNotIn("Slump Forecast", res_disabled["reason"])
            
        finally:
            self.db.update_settings(original_settings)

    def test_database_goal_handling(self):
        """Verify micro-goal set/get and clean serialization."""
        orig_goal = self.db.get_current_goal()
        try:
            self.db.set_current_goal("Test Goal")
            self.assertEqual(self.db.get_current_goal(), "Test Goal")
            self.db.set_current_goal("")
            self.assertEqual(self.db.get_current_goal(), "")
        finally:
            self.db.set_current_goal(orig_goal)

    def test_database_hydration_handling(self):
        """Verify daily hydration resetting and increment safety."""
        with self.db.connection() as conn:
            conn.execute("DELETE FROM hydration")
        
        # 1. Fresh state today
        hyd = self.db.get_hydration()
        self.assertEqual(hyd["cups"], 0.0)
        self.assertEqual(hyd["date"], datetime.today().date().isoformat())
        
        # 2. Increment
        self.db.increment_hydration()
        self.assertEqual(self.db.get_hydration()["cups"], 1.0)
        
        # 3. Reset on new day
        with self.db.connection() as conn:
            conn.execute("DELETE FROM hydration")
            conn.execute("INSERT OR REPLACE INTO hydration (date, cups) VALUES (?, ?)", ("2020-01-01", 5.0))
        hyd_new = self.db.get_hydration()
        self.assertEqual(hyd_new["cups"], 0.0)
        self.assertEqual(hyd_new["date"], datetime.today().date().isoformat())


class TestMindFlowAPI(unittest.TestCase):
    def setUp(self):
        from backend.server import SHARED_API_TOKEN
        self.raw_client = flask_app.test_client()
        
        class TokenClient:
            def __init__(self, client, token):
                self.client = client
                self.token = token
            def get(self, *args, **kwargs):
                headers = kwargs.setdefault("headers", {})
                headers["X-MIND-FLOW-TOKEN"] = self.token
                return self.client.get(*args, **kwargs)
            def post(self, *args, **kwargs):
                headers = kwargs.setdefault("headers", {})
                headers["X-MIND-FLOW-TOKEN"] = self.token
                return self.client.post(*args, **kwargs)
            def put(self, *args, **kwargs):
                headers = kwargs.setdefault("headers", {})
                headers["X-MIND-FLOW-TOKEN"] = self.token
                return self.client.put(*args, **kwargs)
            def delete(self, *args, **kwargs):
                headers = kwargs.setdefault("headers", {})
                headers["X-MIND-FLOW-TOKEN"] = self.token
                return self.client.delete(*args, **kwargs)
        
        self.client = TokenClient(self.raw_client, SHARED_API_TOKEN)
        self.db = server_db
        # Backup shared state
        self.original_state = shared_state.copy()
        clear_db(self.db)
        
    def tearDown(self):
        # Restore shared state
        for k, v in self.original_state.items():
            shared_state[k] = v
        clear_db(self.db)

    def test_require_api_token(self):
        # 1. Accessing without token should return 401
        res = self.raw_client.get('/api/status')
        self.assertEqual(res.status_code, 401)
        self.assertIn("API token", res.get_json()["error"])
        
        # 2. Accessing with wrong token should return 401
        res = self.raw_client.get('/api/status', headers={"X-MIND-FLOW-TOKEN": "wrong_token"})
        self.assertEqual(res.status_code, 401)

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

    def test_get_status_rest_duration(self):
        with self.db.connection() as conn:
            conn.execute("DELETE FROM sessions")

        try:
            # 2. Configure state to represent an ongoing rest session
            shared_state["current_mode"] = "rest"
            shared_state["elapsed_seconds"] = 45
            shared_state["idle_seconds"] = 165
            shared_state["tracking_active"] = True

            # 3. Call status endpoint
            response = self.client.get('/api/status')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()

            # Verify that rest mode sums the elapsed_seconds (45) instead of the idle_seconds (165)
            self.assertEqual(data["today_rest_seconds"], 45)

            # 4. Call analytics endpoint
            response_an = self.client.get('/api/analytics')
            self.assertEqual(response_an.status_code, 200)
            data_an = response_an.get_json()

            # Verify that the ongoing rest session injected has a duration of 45, not 165
            sessions = data_an["today_sessions"]
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["mode"], "rest")
            self.assertEqual(sessions[0]["duration"], 45)

        finally:
            pass

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
        with self.db.connection() as conn:
            conn.execute("DELETE FROM reflections")

        # Get reflections
        response = self.client.get('/api/reflections')
        self.assertEqual(response.status_code, 200)
        reflections = response.get_json()
        self.assertIsInstance(reflections, list)

        # Post reflection
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
        self.assertIsNone(data["reflection"].get("mood"))

        # Post reflection with mood
        response_mood = self.client.post('/api/reflections', json={
            "energy_level": 3,
            "friction_level": 4,
            "summary": "Testing API Reflection with Mood",
            "mood": "Anxious"
        })
        self.assertEqual(response_mood.status_code, 200)
        data_mood = response_mood.get_json()
        self.assertEqual(data_mood["reflection"]["mood"], "Anxious")

        # Post reflection with invalid mood
        response_inv = self.client.post('/api/reflections', json={
            "energy_level": 3,
            "friction_level": 4,
            "summary": "Testing API Reflection with Invalid Mood",
            "mood": "InvalidMoodVal"
        })
        self.assertEqual(response_inv.status_code, 200)
        data_inv = response_inv.get_json()
        self.assertIsNone(data_inv["reflection"]["mood"])
        
        # Missing param
        response2 = self.client.post('/api/reflections', json={
            "energy_level": 4
        })
        self.assertEqual(response2.status_code, 400)

    def test_get_analytics(self):
        # Insert a mock app usage entry with mixed categories
        today_str = datetime.today().date().isoformat()
        with self.db.connection() as conn:
            conn.execute("DELETE FROM app_usage")
            conn.execute("""
                INSERT INTO app_usage (date, process, title, titles, duration)
                VALUES (?, ?, ?, ?, ?)
            """, (
                today_str,
                "chrome.exe",
                "YouTube Video - YouTube - Google Chrome",
                json.dumps({
                    "GitHub - code repo": 300,        # work keyword -> 300s work
                    "YouTube Video - YouTube": 60,    # recharge keyword -> 60s recharge
                    "Random page": 10                 # neutral -> 10s neutral
                }),
                370.0
            ))
        
        try:
            response = self.client.get('/api/analytics')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn("reflections", data)
            self.assertIn("weekday_summary", data)
            self.assertIn("recommendations", data)
            self.assertIn("insights", data)
            self.assertIn("app_usage", data)
            self.assertIsInstance(data["app_usage"], list)
            
            # Find the chrome.exe entry
            chrome_entries = [e for e in data["app_usage"] if e["process"] == "chrome.exe"]
            self.assertEqual(len(chrome_entries), 1)
            chrome = chrome_entries[0]
            
            # Assert all the new fields are returned
            self.assertIn("titles", chrome)
            self.assertIn("title_categories", chrome)
            self.assertIn("work_duration", chrome)
            self.assertIn("recharge_duration", chrome)
            self.assertIn("neutral_duration", chrome)
            self.assertIn("category", chrome)
            self.assertIn("week_label", data)
            
            # Check values
            self.assertEqual(chrome["work_duration"], 300)
            self.assertEqual(chrome["recharge_duration"], 60)
            self.assertEqual(chrome["neutral_duration"], 10)
            
            # Classifications check
            self.assertEqual(chrome["title_categories"]["GitHub - code repo"], "work")
            self.assertEqual(chrome["title_categories"]["YouTube Video - YouTube"], "recharge")
            self.assertEqual(chrome["title_categories"]["Random page"], "neutral")
            
            # Predominant category check: work is 300s, recharge is 60s, so it must be "work"
            self.assertEqual(chrome["category"], "work")
            
        finally:
            pass

    def test_get_analytics_with_offset(self):
        # Insert reflections with specific dates (one in current week, one in previous week)
        from datetime import datetime, date, timedelta
        
        today = date.today()
        # Monday of current week
        current_monday = today - timedelta(days=today.weekday())
        
        # Current week reflection
        ts_current = datetime.combine(current_monday, datetime.min.time()).isoformat()
        
        # Previous week reflection
        ts_prev = datetime.combine(current_monday - timedelta(weeks=1), datetime.min.time()).isoformat()
        
        with self.db.connection() as conn:
            conn.execute("DELETE FROM reflections")
            conn.execute("""
                INSERT INTO reflections (timestamp, energy_level, friction_level, summary)
                VALUES (?, ?, ?, ?)
            """, (ts_prev, 3, 4, "[Autopilot] Previous week entry"))
            conn.execute("""
                INSERT INTO reflections (timestamp, energy_level, friction_level, summary)
                VALUES (?, ?, ?, ?)
            """, (ts_current, 4, 2, "Current week entry"))
        
        try:
            # Query current week (week_offset=0)
            response = self.client.get('/api/analytics?week_offset=0')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn("week_label", data)
            self.assertTrue("Current Week" in data["week_label"])
            # Should only contain current week reflection
            self.assertEqual(len(data["reflections"]), 1)
            self.assertEqual(data["reflections"][0]["summary"], "Current week entry")
            
            # Query previous week (week_offset=1)
            response_prev = self.client.get('/api/analytics?week_offset=1')
            self.assertEqual(response_prev.status_code, 200)
            data_prev = response_prev.get_json()
            self.assertIn("week_label", data_prev)
            self.assertFalse("Current Week" in data_prev["week_label"])
            # Should only contain previous week reflection
            self.assertEqual(len(data_prev["reflections"]), 1)
            self.assertEqual(data_prev["reflections"][0]["summary"], "[Autopilot] Previous week entry")
            
        finally:
            pass

    def test_analytics_app_classification(self):
        """Verify that app classification in analytics handles work, recharge, and neutral correctly."""
        original_settings = self.db.get_settings().copy()
        
        self.db.update_settings({
            "work_keywords": ["code.exe", "github"],
            "recharge_keywords": ["steam.exe", "youtube"]
        })
        
        # Inject custom app usage logs
        today_str = datetime.today().date().isoformat()
        with self.db.connection() as conn:
            conn.execute("DELETE FROM app_usage")
            conn.execute("""
                INSERT INTO app_usage (date, process, title, titles, duration)
                VALUES (?, ?, ?, ?, ?)
            """, (today_str, "code.exe", "MIND-FLOW - index.html", json.dumps({"MIND-FLOW - index.html": 1000}), 1000.0))
            conn.execute("""
                INSERT INTO app_usage (date, process, title, titles, duration)
                VALUES (?, ?, ?, ?, ?)
            """, (today_str, "steam.exe", "Steam Store", json.dumps({"Steam Store": 500}), 500.0))
            conn.execute("""
                INSERT INTO app_usage (date, process, title, titles, duration)
                VALUES (?, ?, ?, ?, ?)
            """, (today_str, "explorer.exe", "File Explorer", json.dumps({"File Explorer": 200}), 200.0))
        
        try:
            response = self.client.get('/api/analytics')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            app_usage = data.get("app_usage", [])
            
            # Verify we have entries
            self.assertTrue(len(app_usage) >= 3)
            
            # Check code.exe (should be work)
            code_entry = next(e for e in app_usage if e["process"] == "code.exe")
            self.assertEqual(code_entry["category"], "work")
            self.assertEqual(code_entry["work_duration"], 1000)
            
            # Check steam.exe (should be recharge)
            steam_entry = next(e for e in app_usage if e["process"] == "steam.exe")
            self.assertEqual(steam_entry["category"], "recharge")
            self.assertEqual(steam_entry["recharge_duration"], 500)
            
            # Check explorer.exe (should be neutral)
            explorer_entry = next(e for e in app_usage if e["process"] == "explorer.exe")
            self.assertEqual(explorer_entry["category"], "neutral")
            self.assertEqual(explorer_entry["neutral_duration"], 200)
            
        finally:
            self.db.update_settings(original_settings)

    @patch('backend.database.datetime')
    def test_sleep_recovery_circadian_adaptation(self, mock_datetime):
        """Verify that logging sleep hours and quality adapts the circadian forecast curve correctly."""
        import datetime as dt
        t_now = dt.datetime(2026, 6, 1, 9, 0, 0)
        mock_datetime.now.return_value = t_now
        mock_datetime.fromisoformat.side_effect = lambda x: dt.datetime.fromisoformat(x)
        mock_datetime.today.return_value = t_now
        try:
            with self.db.connection() as conn:
                conn.execute("DELETE FROM reflections")
            
            # 1. Test case: No sleep logged yet (should return None and 0.0 modifier)
            forecast = self.db.get_circadian_forecast()
            self.assertIsNone(forecast["sleep_hours"])
            self.assertIsNone(forecast["sleep_quality"])
            self.assertEqual(forecast["sleep_modifier"], 0.0)
            
            # 2. Test case: Bad sleep (penalty check)
            # 5.0 hours of sleep (2.0h deficit -> -0.5 points)
            # Poor quality (1) (2.0 deficit -> -0.6 points)
            # Total penalty: -1.1 points
            self.db.add_reflection(3, 3, "Poor sleep reflection", sleep_hours=5.0, sleep_quality=1)
            
            forecast_penalty = self.db.get_circadian_forecast()
            self.assertEqual(forecast_penalty["sleep_hours"], 5.0)
            self.assertEqual(forecast_penalty["sleep_quality"], 1)
            self.assertEqual(forecast_penalty["sleep_modifier"], -1.1)
            
            # Peak of fallback circadian curve is normally at hour 10 (value 4.8).
            # With -1.1 penalty, it should be adjusted to 4.8 - 1.1 = 3.7.
            hour_10_energy = forecast_penalty["forecast_curve"][10]["energy"]
            self.assertAlmostEqual(hour_10_energy, 3.7, places=2)
            
            # 3. Test case: API submission
            payload = {
                "energy_level": 4,
                "friction_level": 2,
                "summary": "Good sleep check",
                "mood": "Calm",
                "sleep_hours": 9.0,
                "sleep_quality": 5
            }
            # Clean reflections list for clean test
            with self.db.connection() as conn:
                conn.execute("DELETE FROM reflections")
            
            response = self.client.post('/api/reflections', json=payload)
            self.assertEqual(response.status_code, 200)
            
            # Verify the reflection has stored the sleep values
            reflections = self.db.get_reflections()
            self.assertEqual(len(reflections), 1)
            self.assertEqual(reflections[0]["sleep_hours"], 9.0)
            self.assertEqual(reflections[0]["sleep_quality"], 5)
            
            # Verify the API status returns the updated sleep details in forecast
            status_res = self.client.get('/api/status')
            self.assertEqual(status_res.status_code, 200)
            status_data = status_res.get_json()
            cf = status_data["circadian_forecast"]
            self.assertEqual(cf["sleep_hours"], 9.0)
            self.assertEqual(cf["sleep_quality"], 5)
            # 9.0 hours sleep -> +0.15 modifier. 5 quality -> +0.2 modifier. Total +0.35.
            self.assertEqual(cf["sleep_modifier"], 0.35)
            
        finally:
            pass

    @patch('backend.database.datetime')
    def test_hydration_energy_synergy_and_timer_adaptation(self, mock_datetime):
        """Verify that hydration progress, expectations, and timer modifications work correctly."""
        import datetime as dt
        # Mock current time to 12:00 PM (hour 12)
        t_now = datetime(2026, 6, 1, 12, 0, 0)
        mock_datetime.now.return_value = t_now
        mock_datetime.fromisoformat.side_effect = lambda x: datetime.fromisoformat(x)
        mock_datetime.today.return_value = t_now
        
        original_settings = self.db.get_settings().copy()
        
        try:
            # 1. Reset hydration
            with self.db.connection() as conn:
                conn.execute("DELETE FROM hydration")
                conn.execute("INSERT OR REPLACE INTO hydration (date, cups) VALUES (?, ?)", ("2026-06-01", 0.0))
            
            # Target is 8 cups. Hour is 12. Active day: 8:00 AM to 10:00 PM (14 hours elapsed).
            # Expected fraction: (12 - 8) / 14 = 4 / 14 = 0.2857.
            # Expected amount: 8 * 4 / 14 = 2.29.
            # Logged: 0 cups. Ratio: 0 / 2.29 = 0.0 (dehydrated).
            # Penalty should be -0.30 since current_hour >= 10.
            forecast = self.db.get_circadian_forecast()
            self.assertEqual(forecast["hydration_cups"], 0.0)
            self.assertEqual(forecast["hydration_modifier"], -0.30)
            
            # Check curve shift at hour 10: 4.8 baseline - 0.3 = 4.5
            hour_10_energy = forecast["forecast_curve"][10]["energy"]
            self.assertAlmostEqual(hour_10_energy, 4.5, places=2)
            
            # 2. Check Autopilot timer adjustments (work sprint -5m, rest break +15s)
            self.db.update_settings({
                "work_duration_minutes": 45,
                "rest_duration_seconds": 20,
                "circadian_forecast_enabled": False
            })
            self.db._adaptive_cache["result"] = None
            times = self.db.get_adaptive_times()
            self.assertEqual(times["work_modifier"], -5)
            self.assertEqual(times["rest_modifier"], 15)
            self.assertIn("Dehydration", times["reason"])
            
            # 3. Log water to trigger optimal hydration bonus
            # If we log 3 cups, ratio = 3 / 2.29 = 1.31 >= 0.9.
            # Modifier should be +0.15.
            with self.db.connection() as conn:
                conn.execute("INSERT OR REPLACE INTO hydration (date, cups) VALUES (?, ?)", ("2026-06-01", 3.0))
            
            self.db._adaptive_cache["result"] = None
            forecast_hydrated = self.db.get_circadian_forecast()
            self.assertEqual(forecast_hydrated["hydration_cups"], 3.0)
            self.assertEqual(forecast_hydrated["hydration_modifier"], 0.15)
            
            # Check curve shift at hour 10: 4.8 baseline + 0.15 = 4.95
            hour_10_energy_hydrated = forecast_hydrated["forecast_curve"][10]["energy"]
            self.assertAlmostEqual(hour_10_energy_hydrated, 4.95, places=2)
            
            # Autopilot timers should return to neutral/normal
            self.db._adaptive_cache["result"] = None
            times_hydrated = self.db.get_adaptive_times()
            self.assertEqual(times_hydrated["work_modifier"], 0)
            self.assertEqual(times_hydrated["rest_modifier"], 0)
            
            # 4. Grace period check: mock time to 9:00 AM (hour 9)
            t_morning = datetime(2026, 6, 1, 9, 0, 0)
            mock_datetime.now.return_value = t_morning
            mock_datetime.today.return_value = t_morning
            
            with self.db.connection() as conn:
                conn.execute("INSERT OR REPLACE INTO hydration (date, cups) VALUES (?, ?)", ("2026-06-01", 0.0))
            
            self.db._adaptive_cache["result"] = None
            forecast_morning = self.db.get_circadian_forecast()
            self.assertEqual(forecast_morning["hydration_modifier"], 0.0)
            
            self.db._adaptive_cache["result"] = None
            times_morning = self.db.get_adaptive_times()
            self.assertEqual(times_morning["work_modifier"], 0)
            self.assertEqual(times_morning["rest_modifier"], 0)
            
        finally:
            self.db.update_settings(original_settings)

    @patch('backend.server.os._exit')
    def test_shutdown_app(self, mock_exit):
        response = self.client.post('/api/shutdown')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "shutdown_initiated")
        
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

    def test_manage_goal(self):
        orig_goal = self.db.get_current_goal()
        try:
            # 1. GET returns current goal
            response = self.client.get('/api/goal')
            self.assertEqual(response.status_code, 200)
            self.assertIn("goal", response.get_json())
            
            # 2. POST updates current goal
            response = self.client.post('/api/goal', json={"goal": "Test API goal"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["status"], "success")
            self.assertEqual(response.get_json()["goal"], "Test API goal")
            self.assertEqual(self.db.get_current_goal(), "Test API goal")

            # 3. GET status contains current_goal
            response = self.client.get('/api/status')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["current_goal"], "Test API goal")
        finally:
            self.db.set_current_goal(orig_goal)

    def test_hydration_api(self):
        with self.db.connection() as conn:
            conn.execute("DELETE FROM hydration")
        try:
            # 1. GET returns hydration JSON
            response = self.client.get('/api/hydration')
            self.assertEqual(response.status_code, 200)
            self.assertIn("cups", response.get_json())
            
            # 2. POST increments cups
            cups_before = response.get_json()["cups"]
            response = self.client.post('/api/hydration')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["status"], "success")
            self.assertEqual(response.get_json()["hydration"]["cups"], cups_before + 1.0)
            
            # 3. status contains hydration
            response = self.client.get('/api/status')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["hydration"]["cups"], cups_before + 1.0)

            # 4. POST with custom cups
            response = self.client.post('/api/hydration', json={"cups": 5})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["status"], "success")
            self.assertEqual(response.get_json()["hydration"]["cups"], 5.0)

            # 5. POST with delta increment
            response = self.client.post('/api/hydration', json={"delta": 2.5})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["status"], "success")
            self.assertEqual(response.get_json()["hydration"]["cups"], 7.5) # 5 + 2.5

            # 6. POST with delta decrement
            response = self.client.post('/api/hydration', json={"delta": -3.0})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["status"], "success")
            self.assertEqual(response.get_json()["hydration"]["cups"], 4.5) # 7.5 - 3.0
        finally:
            pass

class TestAppWindowLaunch(unittest.TestCase):
    @patch('subprocess.Popen')
    def test_launch_app_window_frozen(self, mock_popen):
        import sys
        # Set sys.frozen temporarily
        sys.frozen = True
        try:
            mock_popen.return_value = MagicMock()
            result = launch_app_window("http://localhost:5000")
            self.assertIsNotNone(result)
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            self.assertEqual(args[-2], "--gui")
            self.assertEqual(len(args), 3)
            self.assertEqual(args[0], sys.executable)
        finally:
            if hasattr(sys, 'frozen'):
                del sys.frozen

    @patch('subprocess.Popen')
    def test_launch_app_window_dev(self, mock_popen):
        import sys
        # Ensure sys.frozen does not exist
        if hasattr(sys, 'frozen'):
            del sys.frozen
        mock_popen.return_value = MagicMock()
        result = launch_app_window("http://localhost:5000")
        self.assertIsNotNone(result)
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertEqual(args[-2], "--gui")
        self.assertEqual(args[0], sys.executable)
        self.assertEqual(args[1], sys.argv[0])

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
    @patch('app.db')
    def test_state_machine_tracking_inactive(self, mock_db, mock_idle, mock_proc, mock_title, mock_sleep):
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
        # it transitioned to neutral.
        self.assertEqual(shared_state["current_mode"], "neutral")
        mock_db.log_session.assert_called()

    @patch('app.time.sleep')
    @patch('app.get_active_window_title')
    @patch('app.get_active_process_name')
    @patch('app.get_idle_seconds')
    @patch('app.db')
    def test_state_machine_work_transition(self, mock_db, mock_idle, mock_proc, mock_title, mock_sleep):
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

    @patch('app.time.sleep')
    @patch('app.get_active_window_title')
    @patch('app.get_active_process_name')
    @patch('app.get_idle_seconds')
    @patch('app.db')
    @patch('app.datetime')
    def test_state_machine_rest_transition_retroactive_adjust(self, mock_datetime, mock_db, mock_idle, mock_proc, mock_title, mock_sleep):
        mock_db.get_settings.return_value = {
            "work_keywords": ["code.exe"],
            "recharge_keywords": ["game.exe"],
            "idle_timeout_seconds": 120
        }
        mock_db.get_adaptive_times.return_value = {
            "work_minutes": 45,
            "rest_seconds": 20,
            "reason": "Default"
        }
        mock_db.get_reflections.return_value = []
        
        # Start in work mode, and transition to rest
        shared_state["tracking_active"] = True
        shared_state["current_mode"] = "work"
        
        mock_title.return_value = "Idle State"
        mock_proc.return_value = "System"
        mock_idle.return_value = 130.0  # Greater than 120s limit
        
        # Mock datetime now calls
        import datetime as dt
        t_start = datetime(2026, 6, 1, 10, 0, 0)
        
        # We need mock_datetime.now to return t_start first, then t_start + 300s
        call_times = [t_start, t_start + dt.timedelta(seconds=300)]
        call_index = 0
        def mock_now():
            nonlocal call_index
            val = call_times[min(call_index, len(call_times) - 1)]
            call_index += 1
            return val
        mock_datetime.now.side_effect = mock_now
        
        # Maintain fromisoformat
        mock_datetime.fromisoformat.side_effect = lambda x: datetime.fromisoformat(x)
        
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
            
        # Verify transition to rest occurred
        self.assertEqual(shared_state["current_mode"], "rest")
        
        # Verify log_session was called with adjusted end_time
        mock_db.log_session.assert_called()
        call_args = mock_db.log_session.call_args[0]
        # Arguments: mode, start_time, end_time
        self.assertEqual(call_args[0], "neutral")
        start_time, end_time = call_args[1], call_args[2]
        
        # The start_time of work is t_start.
        # The transition_time is now (t_start + 300s) - idle_limit (120s) = t_start + 180s
        self.assertEqual(start_time, t_start)
        self.assertEqual(end_time, t_start + dt.timedelta(seconds=180))


class TestConcurrencyAndPathPortability(unittest.TestCase):
    def test_database_list_accessors_thread_safety(self):
        """Verify that get_reflections(), get_sessions(), and get_app_usage() return copies to prevent thread race conditions."""
        db = MindFlowDB()
        try:
            # 1. Reflections copy test
            refs = db.get_reflections()
            self.assertIsInstance(refs, list)
            refs.append({"test": "value"})
            self.assertNotEqual(len(db.get_reflections()), len(refs))
            
            # 2. Sessions copy test
            sess = db.get_sessions()
            self.assertIsInstance(sess, list)
            sess.append({"test": "value"})
            self.assertNotEqual(len(db.get_sessions()), len(sess))
            
            # 3. App usage copy test
            usage = db.get_app_usage()
            self.assertIsInstance(usage, list)
            usage.append({"test": "value"})
            self.assertNotEqual(len(db.get_app_usage()), len(usage))
        finally:
            db.close()

    def test_default_data_dir_portability(self):
        """Verify get_default_data_dir resolves to legacy path or portable paths."""
        from backend.database import get_default_data_dir
        path = get_default_data_dir()
        self.assertTrue(os.path.exists(path) or os.path.basename(path) in ["MIND", ".mindflow"])

    @patch('backend.database.datetime')
    def test_chronological_deficit_bypass_logic(self, mock_datetime):
        """Verify that bypassed breaks are evaluated as a chronological deficit walk."""
        import datetime as dt
        import sqlite3
        t_now = dt.datetime(2026, 6, 1, 9, 0, 0)
        mock_datetime.now.return_value = t_now
        mock_datetime.fromisoformat.side_effect = lambda x: dt.datetime.fromisoformat(x)
        mock_datetime.today.return_value = t_now
        
        master_conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
        db = MindFlowDB()
        try:
            today_date = t_now.date()
            t0 = dt.datetime.combine(today_date, dt.time(9, 0, 0))
            
            # Scenario: completed rest, then bypassed rest. Net bypasses should be 1.
            with db.connection() as conn:
                conn.execute("DELETE FROM sessions")
                conn.execute("""
                    INSERT INTO sessions (mode, start, end, duration, bypassed)
                    VALUES (?, ?, ?, ?, ?)
                """, ("rest", t0.isoformat(), (t0 + dt.timedelta(seconds=20)).isoformat(), 20.0, 0))
                conn.execute("""
                    INSERT INTO sessions (mode, start, end, duration, bypassed)
                    VALUES (?, ?, ?, ?, ?)
                """, ("rest", (t0 + dt.timedelta(minutes=30)).isoformat(), (t0 + dt.timedelta(minutes=30, seconds=20)).isoformat(), 20.0, 1))
            
            db._adaptive_cache["result"] = None
            res = db.get_adaptive_times()
            # Default work: 45.
            # Bypass penalty: -5 (1 bypass).
            # Total work: 45 - 5 = 40.
            self.assertEqual(res["work_minutes"], 40)
            
            # Scenario: bypassed rest, then completed rest. Net bypasses should be 0.
            with db.connection() as conn:
                conn.execute("DELETE FROM sessions")
                conn.execute("""
                    INSERT INTO sessions (mode, start, end, duration, bypassed)
                    VALUES (?, ?, ?, ?, ?)
                """, ("rest", t0.isoformat(), (t0 + dt.timedelta(seconds=20)).isoformat(), 20.0, 1))
                conn.execute("""
                    INSERT INTO sessions (mode, start, end, duration, bypassed)
                    VALUES (?, ?, ?, ?, ?)
                """, ("rest", (t0 + dt.timedelta(minutes=30)).isoformat(), (t0 + dt.timedelta(minutes=30, seconds=20)).isoformat(), 20.0, 0))
            
            # Reset cache because we edited db
            db._adaptive_cache["result"] = None
            res2 = db.get_adaptive_times()
            self.assertEqual(res2["work_minutes"], 45)
            
        finally:
            db.close()
            master_conn.close()

    def test_database_load_corruption_safety(self):
        """Verify that load() creates a backup on JSON corruption instead of wiping database silently."""
        import tempfile
        # Create a temporary file with corrupted JSON content
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"{invalid_json:")
            temp_path = f.name
            
        db = MindFlowDB()
        db.filepath = temp_path
        try:
            with self.assertRaises(Exception):
                db.load()
            
            # Verify that corrupt.bak file was created
            backup_path = temp_path + ".corrupt.bak"
            self.assertTrue(os.path.exists(backup_path))
            
            # Verify that original file was NOT overwritten with default JSON
            with open(temp_path, "r", encoding="utf-8") as f_orig:
                content = f_orig.read()
                self.assertEqual(content, "{invalid_json:")
                
            # Clean up backup
            if os.path.exists(backup_path):
                os.unlink(backup_path)
        finally:
            db.close()
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestZenithIntegration(unittest.TestCase):
    def setUp(self):
        from backend.server import app, db, SHARED_API_TOKEN
        app.config['TESTING'] = True
        raw_client = app.test_client()
        
        class TokenClient:
            def __init__(self, client, token):
                self.client = client
                self.token = token
            def get(self, *args, **kwargs):
                headers = kwargs.setdefault("headers", {})
                headers["X-MIND-FLOW-TOKEN"] = self.token
                return self.client.get(*args, **kwargs)
            def post(self, *args, **kwargs):
                headers = kwargs.setdefault("headers", {})
                headers["X-MIND-FLOW-TOKEN"] = self.token
                return self.client.post(*args, **kwargs)
            def put(self, *args, **kwargs):
                headers = kwargs.setdefault("headers", {})
                headers["X-MIND-FLOW-TOKEN"] = self.token
                return self.client.put(*args, **kwargs)
            def delete(self, *args, **kwargs):
                headers = kwargs.setdefault("headers", {})
                headers["X-MIND-FLOW-TOKEN"] = self.token
                return self.client.delete(*args, **kwargs)
                
        self.client = TokenClient(raw_client, SHARED_API_TOKEN)
        self.db = db
        clear_db(self.db)

    def tearDown(self):
        clear_db(self.db)

    def test_database_vitality_methods(self):
        # Test steps logging
        self.db.log_steps(5000, "2026-06-01")
        self.assertEqual(self.db.get_steps("2026-06-01"), 5000)
        
        # Test sleep logging
        self.db.log_sleep(7.5, 4, "2026-06-01")
        sleep_info = self.db.get_sleep("2026-06-01")
        self.assertEqual(sleep_info["hours"], 7.5)
        self.assertEqual(sleep_info["quality"], 4)

    def test_zen_level_adaptive_timers(self):
        # 1. Test "tranquil" zen_level: work limit should be 35m, rest limit 30s
        self.db.update_settings({
            "zen_level": "tranquil",
            "adaptive_timers_enabled": True
        })
        self.db._adaptive_cache["result"] = None
        times = self.db.get_adaptive_times()
        
        # Disable autopilot to check static overrides
        self.db.update_settings({
            "adaptive_timers_enabled": False
        })
        self.db._adaptive_cache["result"] = None
        times_static = self.db.get_adaptive_times()
        self.assertEqual(times_static["work_minutes"], 35)
        self.assertEqual(times_static["rest_seconds"], 30)

        # 2. Test "sprint" zen_level
        self.db.update_settings({
            "zen_level": "sprint",
            "adaptive_timers_enabled": False
        })
        self.db._adaptive_cache["result"] = None
        times_sprint = self.db.get_adaptive_times()
        self.assertEqual(times_sprint["work_minutes"], 55)
        self.assertEqual(times_sprint["rest_seconds"], 15)

    def test_vitality_endpoints(self):
        # Test GET /api/vitality
        res_get = self.client.get('/api/vitality')
        self.assertEqual(res_get.status_code, 200)
        
        # Test POST /api/vitality
        payload = {
            "steps": 12000,
            "sleep_hours": 8.5,
            "sleep_quality": 5
        }
        res_post = self.client.post('/api/vitality', json=payload)
        self.assertEqual(res_post.status_code, 200)
        data = res_post.get_json()
        self.assertEqual(data["steps"], 12000)
        self.assertEqual(data["sleep_hours"], 8.5)
        self.assertEqual(data["sleep_quality"], 5)

        # Verify database is updated
        from datetime import date
        today_str = date.today().isoformat()
        self.assertEqual(self.db.get_steps(today_str), 12000)
        sleep_info = self.db.get_sleep(today_str)
        self.assertEqual(sleep_info["hours"], 8.5)
        self.assertEqual(sleep_info["quality"], 5)


class TestWorkspaceManager(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.test_dir = tempfile.mkdtemp()
        self.profiles_dir = os.path.join(self.test_dir, "Workspace_Profiles")
        
        # Create profile dirs
        os.makedirs(os.path.join(self.profiles_dir, "Work"))
        os.makedirs(os.path.join(self.profiles_dir, "Recharge"))
        
        # Create some mock profile files
        with open(os.path.join(self.profiles_dir, "Work", "Work_Readme.txt"), "w") as f:
            f.write("readme")
        with open(os.path.join(self.profiles_dir, "Work", "project.lnk"), "w") as f:
            f.write("shortcut")
        with open(os.path.join(self.profiles_dir, "Recharge", "Recharge_Readme.txt"), "w") as f:
            f.write("readme")
        with open(os.path.join(self.profiles_dir, "Recharge", "game.lnk"), "w") as f:
            f.write("shortcut")

        from backend.workspace_manager import WorkspaceManager
        self.mgr = WorkspaceManager(self.test_dir)
        # Mock desktop path to our temp directory to avoid touching the actual desktop
        self.mgr.desktop_dir = os.path.join(self.test_dir, "MockDesktop")
        os.makedirs(self.mgr.desktop_dir, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir)

    def test_workspace_swapping_and_sweeping(self):
        # 1. Transition neutral -> work
        self.mgr.transition_workspace("neutral", "work")
        
        # Verify project.lnk is moved to Desktop
        self.assertTrue(os.path.exists(os.path.join(self.mgr.desktop_dir, "project.lnk")))
        # Verify Work_Readme.txt is NOT moved to Desktop
        self.assertFalse(os.path.exists(os.path.join(self.mgr.desktop_dir, "Work_Readme.txt")))
        # Verify project.lnk is no longer in Work profile folder
        self.assertFalse(os.path.exists(os.path.join(self.profiles_dir, "Work", "project.lnk")))
        
        # Verify registry entry
        reg = self.mgr._load_registry()
        self.assertEqual(reg["work"], ["project.lnk"])

        # 2. Transition work -> recharge
        self.mgr.transition_workspace("work", "recharge")
        
        # Verify project.lnk is swept back to Work profile folder
        self.assertTrue(os.path.exists(os.path.join(self.profiles_dir, "Work", "project.lnk")))
        self.assertFalse(os.path.exists(os.path.join(self.mgr.desktop_dir, "project.lnk")))
        
        # Verify game.lnk is moved to Desktop
        self.assertTrue(os.path.exists(os.path.join(self.mgr.desktop_dir, "game.lnk")))
        self.assertFalse(os.path.exists(os.path.join(self.mgr.desktop_dir, "Recharge_Readme.txt")))
        
        # Verify registry entries
        reg = self.mgr._load_registry()
        self.assertEqual(reg["work"], [])
        self.assertEqual(reg["recharge"], ["game.lnk"])

        # 3. Transition recharge -> neutral
        self.mgr.transition_workspace("recharge", "neutral")
        
        # Verify game.lnk is swept back to Recharge profile folder
        self.assertTrue(os.path.exists(os.path.join(self.profiles_dir, "Recharge", "game.lnk")))
        self.assertFalse(os.path.exists(os.path.join(self.mgr.desktop_dir, "game.lnk")))
        
        # Verify registry is empty
        reg = self.mgr._load_registry()
        self.assertEqual(reg["work"], [])
        self.assertEqual(reg["recharge"], [])

    def test_workspace_startup_cleanup(self):
        # Manually simulate a crash: register game.lnk as swapped and place it on desktop
        reg = self.mgr._load_registry()
        reg["recharge"] = ["game.lnk"]
        self.mgr._save_registry(reg)
        
        # Move game.lnk to Desktop manually
        import shutil
        shutil.move(os.path.join(self.profiles_dir, "Recharge", "game.lnk"), os.path.join(self.mgr.desktop_dir, "game.lnk"))
        
        self.assertTrue(os.path.exists(os.path.join(self.mgr.desktop_dir, "game.lnk")))
        self.assertFalse(os.path.exists(os.path.join(self.profiles_dir, "Recharge", "game.lnk")))
        
        # Run startup sweep
        self.mgr.sweep_back_all()
        
        # Verify file is back in Recharge folder and registry is cleared
        self.assertTrue(os.path.exists(os.path.join(self.profiles_dir, "Recharge", "game.lnk")))
        self.assertFalse(os.path.exists(os.path.join(self.mgr.desktop_dir, "game.lnk")))
        reg_cleared = self.mgr._load_registry()
        self.assertEqual(reg_cleared["recharge"], [])
class TestCognitiveBattery(unittest.TestCase):
    def test_battery_math_work(self):
        from app import CognitiveBattery
        battery = CognitiveBattery(capacity=100.0, consecutive_work=0.0)
        cap, streak = battery.process_tick(is_working=True, elapsed_minutes=10.0)
        self.assertEqual(streak, 10.0)
        self.assertEqual(cap, 93.25)

    def test_battery_math_rest(self):
        from app import CognitiveBattery
        battery = CognitiveBattery(capacity=90.0, consecutive_work=10.0)
        cap, streak = battery.process_tick(is_working=False, elapsed_minutes=2.0)
        self.assertEqual(streak, 0.0)
        self.assertEqual(cap, 95.0)

    def test_db_battery_state(self):
        from backend.database import MindFlowDB
        db = MindFlowDB()
        # Clear/initialize battery state database row for this test
        with db.connection() as conn:
            conn.execute("UPDATE battery_state SET current_capacity = 100.0, consecutive_work_minutes = 0.0 WHERE id = 1")
        
        state = db.get_battery_state()
        self.assertEqual(state["capacity"], 100.0)
        self.assertEqual(state["consecutive_work"], 0.0)
        
        db.flush_battery_state(85.5, 12.3)
        state = db.get_battery_state()
        self.assertEqual(state["capacity"], 85.5)
        self.assertEqual(state["consecutive_work"], 12.3)

    def test_api_battery_status(self):
        from backend.server import app, shared_state, SHARED_API_TOKEN
        shared_state["battery_capacity"] = 75.0
        shared_state["battery_consecutive_work"] = 15.0
        with app.test_client() as client:
            resp = client.get("/api/status", headers={"X-MIND-FLOW-TOKEN": SHARED_API_TOKEN})
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertEqual(data["battery_capacity"], 75.0)
            self.assertEqual(data["consecutive_work_minutes"], 15.0)
            self.assertEqual(data["current_energy"], 3.75)

    def test_context_aware_activity_classification(self):
        from backend.database import MindFlowDB
        db = MindFlowDB()
        from app import classify_activity_mode
        work_keywords = ["vs code", "pycharm", "github", "stack overflow"]
        recharge_keywords = ["youtube", "netflix", "steam"]
        
        # Youtube but contains godot tutorial -> Work
        mode = classify_activity_mode("chrome.exe", "Godot Game Engine Tutorial - YouTube", work_keywords, recharge_keywords)
        self.assertEqual(mode, "work")
        
        # Non-browser dev process (vscode) -> Work
        mode = classify_activity_mode("code.exe", "index.js - Project", work_keywords, recharge_keywords)
        self.assertEqual(mode, "work")
        
        # Youtube without work context -> Recharge
        mode = classify_activity_mode("chrome.exe", "Funny Cat Videos - YouTube", work_keywords, recharge_keywords)
        self.assertEqual(mode, "recharge")
        
        # Stackoverflow page -> Work (falls out of Neutral Blackhole)
        mode = classify_activity_mode("firefox", "How to sort dict in Python - Stack Overflow", work_keywords, recharge_keywords)
        self.assertEqual(mode, "work")
        
        # Custom user regex rule
        original_settings = db.get_settings().copy()
        try:
            db.update_settings({
                "custom_rules": [{"pattern": "reddit\\.com/r/programming", "category": "work"}]
            })
            mode = classify_activity_mode("chrome.exe", "programming news on reddit.com/r/programming", work_keywords, recharge_keywords)
            self.assertEqual(mode, "work")
        finally:
            db.update_settings(original_settings)

    def test_workspace_cloud_sync_and_manifest_recovery(self):
        import tempfile
        import json
        from backend.workspace_manager import WorkspaceManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Test cloud sync path detection
            wm = WorkspaceManager(tmpdir)
            wm.desktop_dir = os.path.join(tmpdir, "OneDrive", "Desktop")
            self.assertTrue(wm.detect_cloud_sync())
            
            # Non cloud sync
            wm.desktop_dir = os.path.join(tmpdir, "Desktop")
            self.assertFalse(wm.detect_cloud_sync())
            
            # 2. Test manifest recovery
            wm.desktop_dir = os.path.join(tmpdir, "Desktop")
            os.makedirs(wm.desktop_dir, exist_ok=True)
            
            # Create a file in profile
            profile_work = os.path.join(wm.profiles_dir, "Work")
            os.makedirs(profile_work, exist_ok=True)
            test_file = os.path.join(profile_work, "stranded.txt")
            with open(test_file, "w") as f:
                f.write("stranded content")
                
            # Create a fake manifest representing a crash during transition to Desktop
            target_dest = os.path.join(wm.desktop_dir, "stranded.txt")
            manifest = [{"src": test_file, "dst": target_dest}]
            with open(wm.manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f)
                
            # Trigger recovery
            wm.recover_stranded_files()
            
            # Verify file was moved to destination and manifest cleared
            self.assertTrue(os.path.exists(target_dest))
            self.assertFalse(os.path.exists(test_file))
            self.assertFalse(os.path.exists(wm.manifest_path))

    def test_hydration_sleep_averages_fallbacks(self):
        from backend.database import MindFlowDB
        db = MindFlowDB()
        import datetime
        from datetime import date
        
        # Clear database records
        with db.connection() as conn:
            conn.execute("DELETE FROM hydration")
            conn.execute("DELETE FROM reflections")
            
        today_str = date.today().isoformat()
        
        # 1. Test hydration fallback: no record today, but has historical logs
        # Log 8 cups yesterday
        yesterday_str = (date.today() - datetime.timedelta(days=1)).isoformat()
        with db.connection() as conn:
            conn.execute("INSERT INTO hydration (date, cups) VALUES (?, ?)", (yesterday_str, 8.0))
            
        # Context ratio uses 8.0 cups average, meaning no penalty (ratio >= 0.9)
        hyd_ctx = db._get_hydration_context(datetime.datetime.now())
        self.assertEqual(hyd_ctx["modifier"], 0.15)
        
        # 2. Test hydration fallback: no logs at all -> modifier is 0.0 (no penalty)
        with db.connection() as conn:
            conn.execute("DELETE FROM hydration")
        hyd_ctx = db._get_hydration_context(datetime.datetime.now())
        self.assertEqual(hyd_ctx["modifier"], 0.0)
        
        # 3. Test sleep fallback: no logs today, but has historical sleep log
        # Log 8 hours sleep yesterday
        yesterday_dt = datetime.datetime.now() - datetime.timedelta(days=1)
        db.add_reflection(5, 1, "test sleep history", sleep_hours=8.0, sleep_quality=4)
        # Force timestamp to yesterday
        with db.connection() as conn:
            conn.execute("UPDATE reflections SET timestamp = ? WHERE id = (SELECT max(id) FROM reflections)", (yesterday_dt.isoformat(),))
            
        forecast = db.get_circadian_forecast()
        # Fallback should read yesterday's sleep
        self.assertEqual(forecast["sleep_hours"], 8.0)
        self.assertEqual(forecast["sleep_quality"], 4)
        self.assertGreater(forecast["sleep_modifier"], 0.0)


if __name__ == "__main__":
    unittest.main()
