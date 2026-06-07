import os
import sys
import json
import re
import tempfile
import threading
import copy
import time
from datetime import datetime

def get_default_data_dir():
    legacy_dir = r"C:\MIND"
    if os.path.exists(legacy_dir) and os.path.isdir(legacy_dir):
        return legacy_dir
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if appdata:
            return os.path.join(appdata, "MIND")
    home = os.path.expanduser("~")
    return os.path.join(home, ".mindflow")

DEFAULT_DATA_DIR = get_default_data_dir()
DB_FILE = os.getenv("MINDFLOW_DB_FILE", os.path.join(DEFAULT_DATA_DIR, "mind_flow_data.json"))

_keyword_regex_cache = {}
_combined_regex_cache = {}
_simulated_disk = {}

def matches_any_keyword(keywords_list, text):
    """Check if any keyword in keywords_list matches a target text respecting word boundaries."""
    if not isinstance(text, str) or not keywords_list:
        return False
    
    # Convert list to tuple to make it hashable for the cache key
    cache_key = tuple(keywords_list)
    if cache_key not in _combined_regex_cache:
        patterns = []
        for kw in keywords_list:
            if not isinstance(kw, str):
                continue
            kw = kw.strip().lower()
            if not kw:
                continue
            escaped_kw = re.escape(kw)
            left_boundary = r"(?<![a-zA-Z0-9])" if kw[0].isalnum() else ""
            right_boundary = r"(?![a-zA-Z0-9])" if kw[-1].isalnum() else ""
            patterns.append(f"(?:{left_boundary}{escaped_kw}{right_boundary})")
        if patterns:
            _combined_regex_cache[cache_key] = re.compile("|".join(patterns))
        else:
            _combined_regex_cache[cache_key] = None
            
    regex = _combined_regex_cache[cache_key]
    if not regex:
        return False
    return bool(regex.search(text.lower()))

def matches_keyword(kw, text):
    """Check if a keyword matches a target text respecting word boundaries."""
    if not isinstance(kw, str) or not isinstance(text, str):
        return False
    kw = kw.strip().lower()
    text = text.lower()
    if not kw:
        return False
    if kw not in _keyword_regex_cache:
        escaped_kw = re.escape(kw)
        left_boundary = r"(?<![a-zA-Z0-9])" if kw and kw[0].isalnum() else ""
        right_boundary = r"(?![a-zA-Z0-9])" if kw and kw[-1].isalnum() else ""
        pattern = f"{left_boundary}{escaped_kw}{right_boundary}"
        _keyword_regex_cache[kw] = re.compile(pattern)
    return bool(_keyword_regex_cache[kw].search(text))

DEFAULT_SETTINGS = {
    "work_keywords": [
        "vs code", "visual studio", "pycharm", "intellij", "sublime", "notepad++", 
        "eclipse", "word", "excel", "powerpoint", "pdf", "stack overflow", 
        "github", "google docs", "jupyter", "overleaf", "antigravity"
    ],
    "recharge_keywords": [
        "steam", "vlc", "netflix", "youtube", "spotify", "discord", "twitch", 
        "crunchyroll", "anime", "epic games", "gog galaxy", "xbox"
    ],
    "work_duration_minutes": 45,
    "idle_timeout_seconds": 180,
    "adaptive_timers_enabled": True,
    "rest_duration_seconds": 20,
    "eye_care_mode": False,
    "hydration_target": 8,
    "hydration_unit": "cups",
    "hydration_increment": 1,
    "circadian_forecast_enabled": True,
    "circadian_forecast_sensitivity": "medium"
}

DEFAULT_CIRCADIAN_CURVE = {
    0: 1.5, 1: 1.2, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.2,
    6: 2.0, 7: 3.0, 8: 3.8, 9: 4.5, 10: 4.8, 11: 4.6,
    12: 3.8, 13: 3.2, 14: 3.0, 15: 3.6, 16: 4.0, 17: 4.2,
    18: 4.0, 19: 3.6, 20: 3.2, 21: 2.8, 22: 2.2, 23: 1.8
}

class MindFlowDB:
    file_lock = threading.RLock() # Class-level lock to serialize background disk writes across all DB instances

    def __init__(self):
        self.lock = threading.RLock()
        self.filepath = DB_FILE
        self.data = {
            "settings": DEFAULT_SETTINGS.copy(),
            "sessions": [],
            "reflections": [],
            "app_usage": [],
            "current_goal": "",
            "hydration": {"date": "", "cups": 0}
        }
        self._save_event = threading.Event()
        self._bg_writer_thread = None
        if self.filepath != ":memory:":
            self._bg_writer_thread = threading.Thread(target=self._bg_writer_worker, daemon=True)
            self._bg_writer_thread.start()
        self._adaptive_cache = {
            "last_settings": None,
            "last_sessions_len": -1,
            "last_reflections_len": -1,
            "last_checked_date": None,
            "last_check_time": 0.0,
            "result": None
        }
        self._status_cache = {
            "last_sessions_len": -1,
            "last_reflections_len": -1,
            "last_checked_date": None,
            "last_check_time": 0.0,
            "result": None
        }
        
        # Clean up orphaned temp files from previous runs
        if self.filepath != ":memory:":
            try:
                dir_path = os.path.dirname(self.filepath)
                if os.path.exists(dir_path):
                    for filename in os.listdir(dir_path):
                        if filename.startswith("tmp") and filename.endswith(".json"):
                            try:
                                os.unlink(os.path.join(dir_path, filename))
                            except Exception:
                                pass
            except Exception:
                pass
                
        self.load()

    def load(self):
        with self.lock:
            with MindFlowDB.file_lock:
                if self.filepath == ":memory:":
                    loaded = _simulated_disk.get("data")
                    if loaded is None:
                        self.save(sync=True)
                        return
                    # Merge loaded keys to ensure schema safety
                    loaded_settings = loaded.get("settings")
                    if not isinstance(loaded_settings, dict):
                        loaded_settings = {}
                    self.data["settings"] = {**DEFAULT_SETTINGS, **loaded_settings}
                    
                    loaded_sessions = loaded.get("sessions")
                    self.data["sessions"] = loaded_sessions if isinstance(loaded_sessions, list) else []
                    
                    loaded_reflections = loaded.get("reflections")
                    self.data["reflections"] = loaded_reflections if isinstance(loaded_reflections, list) else []
                    
                    loaded_app_usage = loaded.get("app_usage")
                    self.data["app_usage"] = loaded_app_usage if isinstance(loaded_app_usage, list) else []
                    
                    self.data["current_goal"] = str(loaded.get("current_goal", "") or "")
                    
                    loaded_hydration = loaded.get("hydration")
                    if not isinstance(loaded_hydration, dict):
                        loaded_hydration = {"date": "", "cups": 0}
                    self.data["hydration"] = loaded_hydration
                    return

                if os.path.exists(self.filepath):
                    try:
                        with open(self.filepath, "r", encoding="utf-8") as f:
                            loaded = json.load(f)
                            if not isinstance(loaded, dict):
                                loaded = {}
                            
                            # Merge loaded keys to ensure schema safety
                            loaded_settings = loaded.get("settings")
                            if not isinstance(loaded_settings, dict):
                                loaded_settings = {}
                            self.data["settings"] = {**DEFAULT_SETTINGS, **loaded_settings}
                            
                            loaded_sessions = loaded.get("sessions")
                            self.data["sessions"] = loaded_sessions if isinstance(loaded_sessions, list) else []
                            
                            loaded_reflections = loaded.get("reflections")
                            self.data["reflections"] = loaded_reflections if isinstance(loaded_reflections, list) else []
                            
                            loaded_app_usage = loaded.get("app_usage")
                            self.data["app_usage"] = loaded_app_usage if isinstance(loaded_app_usage, list) else []
                            
                            self.data["current_goal"] = str(loaded.get("current_goal", "") or "")
                            
                            loaded_hydration = loaded.get("hydration")
                            if not isinstance(loaded_hydration, dict):
                                loaded_hydration = {"date": "", "cups": 0}
                            self.data["hydration"] = loaded_hydration
                    except Exception as e:
                        print(f"Error loading database, resetting to default: {e}")
                        self.save(sync=True)
                else:
                    self.save(sync=True)

    def _bg_write(self, data_to_write):
        with MindFlowDB.file_lock:
            try:
                dir_path = os.path.dirname(self.filepath)
                os.makedirs(dir_path, exist_ok=True)
                fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix='.json')
                try:
                    with os.fdopen(fd, 'w', encoding='utf-8') as f:
                        json.dump(data_to_write, f, indent=4, ensure_ascii=False)
                    
                    # Robust replace for Windows to handle transient locks (e.g. antivirus/indexers)
                    for attempt in range(5):
                        try:
                            os.replace(tmp_path, self.filepath)
                            break
                        except PermissionError:
                            if attempt == 4:
                                raise
                            time.sleep(0.05)
                except Exception:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    raise
            except Exception as e:
                print(f"Error saving database: {e}")

    def _bg_writer_worker(self):
        while True:
            self._save_event.wait()
            self._save_event.clear()
            # Coalesce window (e.g., 0.1 seconds) to allow rapid writes to group together
            time.sleep(0.1)
            # Drain any triggers that occurred during the sleep
            self._save_event.clear()
            
            with self.lock:
                data_to_write = copy.deepcopy(self.data)
            
            self._bg_write(data_to_write)

    def save(self, sync=False):
        """Atomic write to prevent corruption on crash (default: async background)."""
        if self.filepath == ":memory:":
            with self.lock:
                data_copy = copy.deepcopy(self.data)
            with MindFlowDB.file_lock:
                _simulated_disk["data"] = data_copy
            return

        if sync:
            with self.lock:
                data_copy = copy.deepcopy(self.data)
            self._bg_write(data_copy)
            return

        self._save_event.set()

    def get_settings(self):
        with self.lock:
            return self.data["settings"].copy()

    def get_current_goal(self):
        with self.lock:
            return self.data.get("current_goal", "")

    def set_current_goal(self, goal):
        with self.lock:
            self.data["current_goal"] = str(goal).strip()
        self.save()

    def get_hydration(self):
        with self.lock:
            today_str = datetime.today().date().isoformat()
            hyd = self.data.setdefault("hydration", {"date": today_str, "cups": 0})
            if not isinstance(hyd, dict):
                hyd = {"date": today_str, "cups": 0}
                self.data["hydration"] = hyd
            if hyd.get("date") != today_str:
                hyd["date"] = today_str
                hyd["cups"] = 0
                self.save()
            
            # Return enriched copy
            settings = self.get_settings()
            return {
                "date": hyd["date"],
                "cups": hyd.get("cups", 0),
                "target": settings.get("hydration_target", 8),
                "unit": settings.get("hydration_unit", "cups"),
                "increment": settings.get("hydration_increment", 1)
            }

    def increment_hydration(self, cups=None):
        with self.lock:
            today_str = datetime.today().date().isoformat()
            hyd = self.data.setdefault("hydration", {"date": today_str, "cups": 0})
            if not isinstance(hyd, dict):
                hyd = {"date": today_str, "cups": 0}
                self.data["hydration"] = hyd
            if hyd.get("date") != today_str:
                hyd["date"] = today_str
                hyd["cups"] = 0
            
            if cups is not None:
                try:
                    val = float(cups)
                    if val.is_integer():
                        val = int(val)
                    hyd["cups"] = max(0, min(10000, val))
                except (ValueError, TypeError):
                    pass
            else:
                inc = self.get_settings().get("hydration_increment", 1)
                try:
                    val = float(hyd.get("cups", 0)) + float(inc)
                    if val.is_integer():
                        val = int(val)
                    hyd["cups"] = min(10000, val)
                except (ValueError, TypeError):
                    pass
            self.save()
            return self.get_hydration()

    def update_settings(self, settings_dict):
        with self.lock:
            for k, v in settings_dict.items():
                if k in DEFAULT_SETTINGS:
                    # Ensure type correctness and range safety to prevent application hangs/lockouts
                    if k in ["work_duration_minutes", "idle_timeout_seconds", "rest_duration_seconds"]:
                        try:
                            val = int(v)
                            if k == "work_duration_minutes":
                                val = max(10, min(180, val))
                            elif k == "idle_timeout_seconds":
                                val = max(10, min(3600, val))
                            elif k == "rest_duration_seconds":
                                val = max(5, min(600, val))
                            self.data["settings"][k] = val
                        except (ValueError, TypeError):
                            pass
                    elif k in ["hydration_target", "hydration_increment"]:
                        try:
                            if k == "hydration_target":
                                val = int(v)
                                val = max(1, min(10000, val))
                            elif k == "hydration_increment":
                                val = float(v)
                                val = max(0.1, min(5000.0, val))
                                if val.is_integer():
                                    val = int(val)
                            self.data["settings"][k] = val
                        except (ValueError, TypeError):
                            pass
                    elif k == "hydration_unit":
                        val = str(v).strip().lower()
                        if val in ["cups", "ml", "oz"]:
                            self.data["settings"][k] = val
                    elif k in ["adaptive_timers_enabled", "eye_care_mode", "circadian_forecast_enabled"]:
                        if isinstance(v, str):
                            self.data["settings"][k] = v.lower() in ["true", "1", "yes"]
                        else:
                            self.data["settings"][k] = bool(v)
                    elif k == "circadian_forecast_sensitivity":
                        val = str(v).strip().lower()
                        if val in ["low", "medium", "high"]:
                            self.data["settings"][k] = val
                    elif isinstance(v, list):
                        # Filter, lowercase, and exclude generic browser names to prevent tracking hijacks
                        disallowed = {"chrome.exe", "chrome", "msedge.exe", "msedge", "firefox.exe", "firefox", "opera.exe", "opera", "brave.exe", "brave", "iexplore.exe", "iexplore", "browser", "explorer"}
                        filtered = [
                            str(x).strip().lower() for x in v 
                            if x and str(x).strip().lower() not in disallowed
                        ]
                        self.data["settings"][k] = filtered[:50]  # Cap keyword count
            self.save()


    def log_session(self, mode, start_time, end_time, brain_dump=None, bypassed=False):
        """
        start_time and end_time should be datetime objects.
        """
        duration = (end_time - start_time).total_seconds()
        if duration < 5:  # Skip logs shorter than 5 seconds to reduce noise
            return
        
        session_entry = {
            "mode": mode,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "duration": duration,
            "brain_dump": brain_dump,
            "bypassed": bypassed
        }
        self.data["sessions"].append(session_entry)
        self.save()

    def add_reflection(self, energy_level, friction_level, summary, mood=None, sleep_hours=None, sleep_quality=None):
        reflection_entry = {
            "timestamp": datetime.now().isoformat(),
            "energy_level": int(energy_level),
            "friction_level": int(friction_level),
            "summary": str(summary).strip(),
            "mood": str(mood).strip() if mood else None,
            "sleep_hours": float(sleep_hours) if sleep_hours is not None else None,
            "sleep_quality": int(sleep_quality) if sleep_quality is not None else None
        }
        self.data["reflections"].append(reflection_entry)
        self.save()
        return reflection_entry

    def get_reflections(self):
        with self.lock:
            return self.data["reflections"].copy()

    def get_sessions(self):
        with self.lock:
            return self.data["sessions"].copy()

    def log_app_usage(self, process, title, duration):
        """
        Logs duration (in seconds) spent on a specific process on the current date.
        """
        if not process or process == "None":
            return
        
        with self.lock:
            today_str = datetime.today().date().isoformat()
            
            # Find if we already have an entry for this process and date (searching in reverse since chronological)
            found = False
            for entry in reversed(self.data.setdefault("app_usage", [])):
                entry_date = entry.get("date")
                if entry_date and entry_date < today_str:
                    break
                if entry_date == today_str and entry.get("process") == process:
                    entry["duration"] = entry.get("duration", 0) + duration
                    
                    # Update titles dictionary
                    titles = entry.setdefault("titles", {})
                    if title and title != "None":
                        titles[title] = titles.get(title, 0) + duration
                        # Update title to the latest active window title (legacy field)
                        entry["title"] = title
                    found = True
                    break
            
            if not found:
                titles = {}
                if title and title != "None":
                    titles[title] = duration
                    
                self.data["app_usage"].append({
                    "date": today_str,
                    "process": process,
                    "title": title if title else "None",
                    "titles": titles,
                    "duration": duration
                })
            
            self.save()

    def get_app_usage(self):
        with self.lock:
            return self.data.setdefault("app_usage", []).copy()

    def _get_hydration_context(self, now=None):
        if now is None:
            now = datetime.now()
        settings = self.get_settings()
        target = settings.get("hydration_target", 8)
        
        today_date = now.date()
        today_str = today_date.isoformat()
        with self.lock:
            hyd = self.data.setdefault("hydration", {"date": today_str, "cups": 0})
            if not isinstance(hyd, dict):
                hyd = {"date": today_str, "cups": 0}
                self.data["hydration"] = hyd
            if hyd.get("date") != today_str:
                cups = 0.0
            else:
                cups = float(hyd.get("cups", 0))
                
        h = now.hour
        if h < 8:
            expected_fraction = 0.0
        elif h >= 22:
            expected_fraction = 1.0
        else:
            expected_fraction = (h - 8) / 14.0
            
        expected_amount = round(target * expected_fraction, 2)
        if expected_amount <= 0.0:
            ratio = 1.0
        else:
            ratio = round(min(1.0, cups / expected_amount), 2)
            
        if cups >= target:
            ratio = 1.0
            
        modifier = 0.0
        if ratio >= 0.9:
            modifier = 0.15
        elif 0.5 <= ratio < 0.9:
            modifier = 0.0
        else:
            if h >= 10:
                modifier = -0.30
                
        return {
            "cups": cups,
            "target": target,
            "expected_amount": expected_amount,
            "ratio": ratio,
            "modifier": modifier
        }

    def get_circadian_forecast(self):
        """
        Calculate circadian fatigue forecast using historical reflection ratings (last 30 days)
        blended with a standard circadian curve, and adapted by last night's sleep context.
        """
        with self.lock:
            # 1. Parse historical reflections grouped by hour of day
            from datetime import timedelta
            now = datetime.now()
            thirty_days_ago = now - timedelta(days=30)
            
            # 1.5 Scan reflections logged today to find the latest sleep details
            today_date = now.date()
            sleep_hours = None
            sleep_quality = None
            sleep_modifier = 0.0
            
            for r in reversed(self.data.get("reflections", [])):
                try:
                    r_dt = datetime.fromisoformat(r["timestamp"])
                    if r_dt.tzinfo is not None:
                        r_dt = r_dt.replace(tzinfo=None)
                    if r_dt.date() == today_date:
                        if r.get("sleep_hours") is not None or r.get("sleep_quality") is not None:
                            sleep_hours = r.get("sleep_hours")
                            sleep_quality = r.get("sleep_quality")
                            break
                    elif r_dt.date() < today_date:
                        break
                except Exception:
                    pass
            
            # Compute Sleep Recovery Modifier
            if sleep_hours is not None or sleep_quality is not None:
                if sleep_hours is not None:
                    if sleep_hours < 7.0:
                        sleep_modifier += (sleep_hours - 7.0) * 0.25
                    elif sleep_hours >= 8.0:
                        sleep_modifier += min(0.3, (sleep_hours - 8.0) * 0.15)
                
                if sleep_quality is not None:
                    if sleep_quality < 3:
                        sleep_modifier += (sleep_quality - 3) * 0.3
                    elif sleep_quality > 3:
                        sleep_modifier += (sleep_quality - 3) * 0.1
                
                # Clamp sleep modifier between -1.5 and +0.5
                sleep_modifier = max(-1.5, min(0.5, sleep_modifier))

            hourly_ratings = {i: [] for i in range(24)}
            for r in self.data.get("reflections", []):
                try:
                    r_dt = datetime.fromisoformat(r["timestamp"])
                    if r_dt.tzinfo is not None:
                        r_dt = r_dt.replace(tzinfo=None)
                    if thirty_days_ago <= r_dt <= now:
                        h = r_dt.hour
                        hourly_ratings[h].append(r["energy_level"])
                except Exception:
                    pass
            
            # 2. Compute blended forecast for all 24 hours
            hyd_ctx = self._get_hydration_context(now)
            hydration_modifier = hyd_ctx["modifier"]
            total_modifier = max(-1.75, min(0.65, sleep_modifier + hydration_modifier))

            forecast_curve = []
            for h in range(24):
                ratings = hourly_ratings[h]
                cnt = len(ratings)
                def_val = DEFAULT_CIRCADIAN_CURVE[h]
                if cnt > 0:
                    avg_historical = sum(ratings) / cnt
                    # Blending weight: max out at 3 samples
                    w = min(1.0, cnt / 3.0)
                    predicted_energy = w * avg_historical + (1.0 - w) * def_val
                else:
                    predicted_energy = def_val
                
                # Apply combined modifier baseline shift
                predicted_energy = max(1.0, min(5.0, predicted_energy + total_modifier))
                
                forecast_curve.append({
                    "hour": h,
                    "energy": round(predicted_energy, 2)
                })
                
            # Helper to interpolate predicted energy at any decimal hour
            def energy_at_hour(hour_val):
                h_floor = int(hour_val) % 24
                h_ceil = (h_floor + 1) % 24
                fraction = hour_val - int(hour_val)
                val_floor = forecast_curve[h_floor]["energy"]
                val_ceil = forecast_curve[h_ceil]["energy"]
                return val_floor * (1.0 - fraction) + val_ceil * fraction
            
            # 3. Impending slump detection (next 90 minutes)
            settings = self.get_settings()
            enabled = settings.get("circadian_forecast_enabled", True)
            sensitivity = settings.get("circadian_forecast_sensitivity", "medium")
            
            # Sensitivity thresholds
            if sensitivity == "low":
                drop_threshold = 0.8
                low_threshold = 2.5
            elif sensitivity == "high":
                drop_threshold = 0.3
                low_threshold = 3.6
            else: # medium
                drop_threshold = 0.5
                low_threshold = 3.2
                
            impending_drop = False
            slump_minutes = 0
            lowest_future_energy = 5.0
            
            current_hour_val = now.hour + now.minute / 60.0
            current_energy = energy_at_hour(current_hour_val)
            
            if enabled:
                # Look ahead in 15-minute intervals up to 90 minutes
                for offset_mins in range(15, 105, 15):
                    future_hour_val = (current_hour_val + offset_mins / 60.0) % 24
                    future_energy = energy_at_hour(future_hour_val)
                    
                    drop = current_energy - future_energy
                    if (drop >= drop_threshold or future_energy <= low_threshold) and future_energy < current_energy:
                        if future_energy < lowest_future_energy:
                            lowest_future_energy = future_energy
                            impending_drop = True
                            slump_minutes = offset_mins
            
            return {
                "forecast_curve": forecast_curve,
                "impending_drop": impending_drop,
                "slump_minutes": slump_minutes,
                "current_predicted_energy": round(current_energy, 2),
                "lowest_predicted_energy": round(lowest_future_energy, 2) if impending_drop else round(current_energy, 2),
                "sleep_hours": sleep_hours,
                "sleep_quality": sleep_quality,
                "sleep_modifier": round(sleep_modifier, 2),
                "hydration_cups": hyd_ctx["cups"],
                "hydration_target": hyd_ctx["target"],
                "expected_hydration": hyd_ctx["expected_amount"],
                "hydration_ratio": hyd_ctx["ratio"],
                "hydration_modifier": round(hydration_modifier, 2)
            }

    def get_adaptive_times(self):
        """Calculate dynamic work minutes and rest seconds based on reflections, bypasses, and circadian forecast."""
        with self.lock:
            settings = self.get_settings()
            
            # Check cache validity
            today_date = datetime.today().date()
            now_time = time.time()
            cache = self._adaptive_cache
            
            if (cache["result"] is not None and
                cache["last_settings"] == settings and
                cache["last_sessions_len"] == len(self.data["sessions"]) and
                cache["last_reflections_len"] == len(self.data["reflections"]) and
                cache["last_checked_date"] == today_date and
                (now_time - cache["last_check_time"]) < 10.0):
                return cache["result"]

            base_work_minutes = settings.get("work_duration_minutes", 45)
            
            if not settings.get("adaptive_timers_enabled", True):
                result = {
                    "work_minutes": base_work_minutes,
                    "work_modifier": 0,
                    "rest_seconds": settings.get("rest_duration_seconds", 20),
                    "rest_modifier": 0,
                    "reason": "Autopilot Off"
                }
                cache["last_settings"] = settings
                cache["last_sessions_len"] = len(self.data["sessions"])
                cache["last_reflections_len"] = len(self.data["reflections"])
                cache["last_checked_date"] = today_date
                cache["last_check_time"] = now_time
                cache["result"] = result
                return result
            
            # Count bypasses today (short-circuiting reverse search since sessions are chronological)
            bypasses_today = 0
            for s in reversed(self.data.get("sessions", [])):
                try:
                    start_dt = datetime.fromisoformat(s["start"])
                    if start_dt.date() == today_date:
                        if s.get("bypassed", False):
                            bypasses_today += 1
                    elif start_dt.date() < today_date:
                        break
                except:
                    pass
            
            # Fetch latest reflection within the last 3 hours
            latest_refl = None
            for r in reversed(self.data.get("reflections", [])):
                try:
                    refl_dt = datetime.fromisoformat(r["timestamp"])
                    age_hours = (datetime.now() - refl_dt).total_seconds() / 3600.0
                    if 0.0 <= age_hours <= 3.0:
                        latest_refl = r
                        break
                    elif age_hours > 3.0:
                        # Since list is chronological, older reflections will only be older
                        break
                except:
                    pass
            
            # Compute Work Sprint Limit
            ref_work_mod = 0
            if latest_refl:
                e = latest_refl.get("energy_level", 3)
                f = latest_refl.get("friction_level", 3)
                if e >= 4 and f <= 2:
                    ref_work_mod = (e - 3) * 5 + (3 - f) * 5
                    ref_work_mod = min(ref_work_mod, 15)
                elif e <= 2 or f >= 4:
                    ref_work_mod = -((3 - e) * 5 + (f - 3) * 5)
                    ref_work_mod = max(ref_work_mod, -15)
            
            bypass_work_mod = -5 * bypasses_today
            bypass_work_mod = max(bypass_work_mod, -15)
            
            # Circadian slump work adjustment
            forecast_adjusted_work = 0
            forecast_adjusted_rest = 0
            if settings.get("circadian_forecast_enabled", True):
                forecast = self.get_circadian_forecast()
                if forecast["impending_drop"]:
                    sensitivity = settings.get("circadian_forecast_sensitivity", "medium")
                    if sensitivity == "low":
                        forecast_adjusted_work = -5
                        forecast_adjusted_rest = 10
                    elif sensitivity == "high":
                        forecast_adjusted_work = -15
                        forecast_adjusted_rest = 25
                    else: # medium
                        forecast_adjusted_work = -10
                        forecast_adjusted_rest = 15

            # Hydration dynamic adjustment
            hydration_work_mod = 0
            hydration_rest_mod = 0
            hyd_ctx = self._get_hydration_context(datetime.now())
            if datetime.now().hour >= 10 and hyd_ctx["ratio"] < 0.5:
                hydration_work_mod = -5
                hydration_rest_mod = 15

            total_work_modifier = ref_work_mod + bypass_work_mod + forecast_adjusted_work + hydration_work_mod
            work_minutes = max(10, min(90, base_work_minutes + total_work_modifier))
            
            # Compute Rest Lockout Duration
            base_rest_seconds = settings.get("rest_duration_seconds", 20)
            ref_rest_mod = 0
            if latest_refl:
                e = latest_refl.get("energy_level", 3)
                f = latest_refl.get("friction_level", 3)
                if e <= 2 or f >= 4:
                    ref_rest_mod = 10
            
            deficit_rest_mod = 10 * bypasses_today
            deficit_rest_mod = min(deficit_rest_mod, 30)
            
            # Dynamic rest modifier based on recent task friction logs
            today_reflections = []
            for r in reversed(self.data.get("reflections", [])):
                try:
                    refl_dt = datetime.fromisoformat(r["timestamp"])
                    if refl_dt.date() == today_date:
                        if not r.get("summary", "").startswith("[Autopilot]"):
                            today_reflections.append(r)
                    elif refl_dt.date() < today_date:
                        break
                except:
                    pass
            avg_friction = sum(r.get("friction_level", 3) for r in today_reflections) / len(today_reflections) if today_reflections else 1.0
            friction_rest_mod = 0
            if avg_friction >= 3.0:
                friction_rest_mod = int((avg_friction - 2.0) * 8)  # 3.0 average friction -> +8s, 4.0 -> +16s, etc.
                friction_rest_mod = min(25, friction_rest_mod)
            
            total_rest_modifier = ref_rest_mod + deficit_rest_mod + friction_rest_mod + forecast_adjusted_rest + hydration_rest_mod
            rest_seconds = min(600, base_rest_seconds + total_rest_modifier)
            
            # Formulate dynamic status reason text
            reasons = []
            if ref_work_mod > 0:
                reasons.append(f"Flow (+{ref_work_mod}m)")
            elif ref_work_mod < 0:
                reasons.append(f"Fatigue ({ref_work_mod}m)")
            
            if bypass_work_mod < 0:
                reasons.append(f"Bypasses ({bypass_work_mod}m)")
                
            if forecast_adjusted_work < 0:
                reasons.append(f"Slump Forecast ({forecast_adjusted_work}m)")
                
            if hydration_work_mod < 0:
                reasons.append(f"Dehydration ({hydration_work_mod}m)")
                
            if ref_rest_mod > 0:
                reasons.append(f"Rest Alert (+{ref_rest_mod}s)")
                
            if deficit_rest_mod > 0:
                reasons.append(f"Rest Deficit (+{deficit_rest_mod}s)")
                
            if friction_rest_mod > 0:
                reasons.append(f"Friction Deficit (+{friction_rest_mod}s)")
                
            if forecast_adjusted_rest > 0:
                reasons.append(f"Rest Pacing (+{forecast_adjusted_rest}s)")
                
            if hydration_rest_mod > 0:
                reasons.append(f"Dehydration Break (+{hydration_rest_mod}s)")
                
            reason_str = " | ".join(reasons) if reasons else "Default"
            
            result = {
                "work_minutes": work_minutes,
                "work_modifier": total_work_modifier,
                "rest_seconds": rest_seconds,
                "rest_modifier": total_rest_modifier,
                "reason": reason_str
            }
            
            cache["last_settings"] = settings
            cache["last_sessions_len"] = len(self.data["sessions"])
            cache["last_reflections_len"] = len(self.data["reflections"])
            cache["last_checked_date"] = today_date
            cache["last_check_time"] = now_time
            cache["result"] = result
            
            return result

    def get_cached_status_data(self):
        """Retrieve pre-computed, cached status stats to avoid parsing entire DB arrays every second."""
        with self.lock:
            today_date = datetime.today().date()
            today_str = today_date.isoformat()
            now_time = time.time()
            
            # Check cache validity
            cache = self._status_cache
            if (cache["result"] is not None and
                cache["last_sessions_len"] == len(self.data["sessions"]) and
                cache["last_reflections_len"] == len(self.data["reflections"]) and
                cache["last_checked_date"] == today_date and
                (now_time - cache.get("last_check_time", 0.0)) < 10.0):
                return cache["result"]
            
            # 1. current_energy for today (reverse search)
            current_energy = 5
            for r in reversed(self.data["reflections"]):
                if r["timestamp"].startswith(today_str):
                    current_energy = r["energy_level"]
                    break
                try:
                    if datetime.fromisoformat(r["timestamp"]).date() < today_date:
                        break
                except:
                    pass
            
            # 2. Detect consecutive high stress (last 2 user reflections)
            latest_user_reflections = []
            for r in reversed(self.data["reflections"]):
                is_auto = r.get("summary", "").startswith("[Autopilot]")
                if not is_auto:
                    latest_user_reflections.append(r)
                    if len(latest_user_reflections) == 2:
                        break
            
            high_stress_alert = False
            latest_mood = None
            if len(latest_user_reflections) >= 1:
                latest_mood = latest_user_reflections[0].get("mood")
                if len(latest_user_reflections) == 2:
                    stress_flags = []
                    for ur in latest_user_reflections:
                        e = ur.get("energy_level", 5)
                        f = ur.get("friction_level", 1)
                        if e <= 2 or f >= 4:
                            stress_flags.append(True)
                        else:
                            stress_flags.append(False)
                    if all(stress_flags):
                        high_stress_alert = True
            
            # 3. Sum up completed sessions today (O(N) reverse search)
            today_work_seconds = 0
            today_recharge_seconds = 0
            today_rest_seconds = 0
            today_bypasses = 0
            
            for s in reversed(self.data["sessions"]):
                if s["start"].startswith(today_str):
                    mode = s["mode"]
                    duration = s["duration"]
                    if mode == "work":
                        today_work_seconds += duration
                    elif mode == "recharge":
                        today_recharge_seconds += duration
                    elif mode == "rest":
                        today_rest_seconds += duration
                    if s.get("bypassed", False):
                        today_bypasses += 1
                else:
                    try:
                        if datetime.fromisoformat(s["start"]).date() < today_date:
                            break
                    except:
                        pass
            
            # 4. Circadian forecast fatigue alert (30 days scan)
            forecast_fatigue_alert = ""
            try:
                from collections import defaultdict
                from datetime import timedelta
                reflections_by_date = defaultdict(list)
                thirty_days_ago = today_date - timedelta(days=30)
                
                for r in reversed(self.data["reflections"]):
                    try:
                        r_dt = datetime.fromisoformat(r["timestamp"])
                        r_date = r_dt.date()
                        if r_date < thirty_days_ago:
                            break
                        if r_date < today_date:
                            reflections_by_date[r_date].append(r["energy_level"])
                    except:
                        pass
                
                if reflections_by_date:
                    avg_past_daily_energy = sum(sum(levels)/len(levels) for levels in reflections_by_date.values()) / len(reflections_by_date)
                    today_levels = []
                    for r in reversed(self.data["reflections"]):
                        if r["timestamp"].startswith(today_str):
                            today_levels.append(r["energy_level"])
                        else:
                            try:
                                r_dt = datetime.fromisoformat(r["timestamp"])
                                if r_dt.date() < today_date:
                                    break
                            except:
                                pass
                    if today_levels:
                        today_avg = sum(today_levels) / len(today_levels)
                        if today_avg < avg_past_daily_energy - 0.5:
                            forecast_fatigue_alert = " (Accumulated fatigue alert: Energy is running lower than your historic average)"
            except Exception:
                pass
            
            # 5. Calculate circadian forecast
            forecast = self.get_circadian_forecast()
            
            # Populate cache
            result = {
                "current_energy": current_energy,
                "high_stress_alert": high_stress_alert,
                "latest_mood": latest_mood,
                "today_work_seconds": today_work_seconds,
                "today_recharge_seconds": today_recharge_seconds,
                "today_rest_seconds": today_rest_seconds,
                "today_bypasses": today_bypasses,
                "forecast_fatigue_alert": forecast_fatigue_alert,
                "circadian_forecast": forecast
            }
            
            cache["last_sessions_len"] = len(self.data["sessions"])
            cache["last_reflections_len"] = len(self.data["reflections"])
            cache["last_checked_date"] = today_date
            cache["last_check_time"] = now_time
            cache["result"] = result
            
            return result


