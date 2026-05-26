import os
import json
import re
import tempfile
import threading
import copy
import time
from datetime import datetime

DB_FILE = r"C:\MIND\mind_flow_data.json"

_keyword_regex_cache = {}

def matches_keyword(kw, text):
    """Check if a keyword matches a target text respecting word boundaries."""
    kw = kw.lower()
    text = text.lower()
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
    "eye_care_mode": False
}

class MindFlowDB:
    file_lock = threading.Lock() # Class-level lock to serialize background disk writes across all DB instances

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
        self.load()

    def load(self):
        with self.lock:
            with MindFlowDB.file_lock:
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

    def save(self, sync=False):
        """Atomic write to prevent corruption on crash (default: async background)."""
        with self.lock:
            data_copy = copy.deepcopy(self.data)
        
        def _bg_write(data_to_write):
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

        if sync:
            _bg_write(data_copy)
        else:
            threading.Thread(target=_bg_write, args=(data_copy,), daemon=True).start()

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
            if hyd.get("date") != today_str:
                hyd["date"] = today_str
                hyd["cups"] = 0
                self.save()
            return hyd

    def increment_hydration(self, cups=None):
        with self.lock:
            hyd = self.get_hydration()
            if cups is not None:
                hyd["cups"] = max(0, min(20, int(cups)))
            else:
                hyd["cups"] = min(20, hyd.get("cups", 0) + 1)
            self.save()
            return hyd

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
            
            # Find if we already have an entry for this process and date
            found = False
            for entry in self.data.setdefault("app_usage", []):
                if entry.get("date") == today_str and entry.get("process") == process:
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

