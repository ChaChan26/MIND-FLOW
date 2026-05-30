import os
import json
import re
import tempfile
import threading
import copy
import time
from datetime import datetime

DB_FILE = os.getenv("MINDFLOW_DB_FILE", r"C:\MIND\mind_flow_data.json")

_keyword_regex_cache = {}
_simulated_disk = {}

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
    "hydration_increment": 1
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
        self._save_in_progress = False
        self._save_requested = False
        
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
                self._save_requested = False
            self._bg_write(data_copy)
            return

        with self.lock:
            self._save_requested = True
            if self._save_in_progress:
                return
            self._save_in_progress = True

        def run_coalesced():
            while True:
                with self.lock:
                    data_to_write = copy.deepcopy(self.data)
                    self._save_requested = False
                
                self._bg_write(data_to_write)
                
                with self.lock:
                    if not self._save_requested:
                        self._save_in_progress = False
                        break

        threading.Thread(target=run_coalesced, daemon=False).start()

    def get_settings(self):
        return self.data["settings"]

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
                elif k in ["adaptive_timers_enabled", "eye_care_mode"]:
                    if isinstance(v, str):
                        self.data["settings"][k] = v.lower() in ["true", "1", "yes"]
                    else:
                        self.data["settings"][k] = bool(v)
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

    def add_reflection(self, energy_level, friction_level, summary):
        reflection_entry = {
            "timestamp": datetime.now().isoformat(),
            "energy_level": int(energy_level),
            "friction_level": int(friction_level),
            "summary": str(summary).strip()
        }
        self.data["reflections"].append(reflection_entry)
        self.save()
        return reflection_entry

    def get_reflections(self):
        return self.data["reflections"]

    def get_sessions(self):
        return self.data["sessions"]

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
            return self.data.setdefault("app_usage", [])

    def get_adaptive_times(self):
        """Calculate dynamic work minutes and rest seconds based on reflections and bypasses."""
        with self.lock:
            settings = self.get_settings()
            base_work_minutes = settings.get("work_duration_minutes", 45)
            
            if not settings.get("adaptive_timers_enabled", True):
                return {
                    "work_minutes": base_work_minutes,
                    "work_modifier": 0,
                    "rest_seconds": 20,
                    "rest_modifier": 0,
                    "reason": "Autopilot Off"
                }
            
            # Count bypasses today (short-circuiting reverse search since sessions are chronological)
            bypasses_today = 0
            today_date = datetime.today().date()
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
                    if age_hours <= 3.0:
                        latest_refl = r
                        break
                    else:
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
            
            total_work_modifier = ref_work_mod + bypass_work_mod
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
            
            total_rest_modifier = ref_rest_mod + deficit_rest_mod
            rest_seconds = min(600, base_rest_seconds + total_rest_modifier)
            
            # Formulate dynamic status reason text
            reasons = []
            if ref_work_mod > 0:
                reasons.append(f"Flow (+{ref_work_mod}m)")
            elif ref_work_mod < 0:
                reasons.append(f"Fatigue ({ref_work_mod}m)")
            
            if bypass_work_mod < 0:
                reasons.append(f"Bypasses ({bypass_work_mod}m)")
                
            if ref_rest_mod > 0:
                reasons.append(f"Rest Alert (+{ref_rest_mod}s)")
                
            if deficit_rest_mod > 0:
                reasons.append(f"Rest Deficit (+{deficit_rest_mod}s)")
                
            reason_str = " | ".join(reasons) if reasons else "Default"
            
            return {
                "work_minutes": work_minutes,
                "work_modifier": total_work_modifier,
                "rest_seconds": rest_seconds,
                "rest_modifier": total_rest_modifier,
                "reason": reason_str
            }

