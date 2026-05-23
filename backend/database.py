import os
import json
import threading
from datetime import datetime

DB_FILE = r"C:\MIND\mind_flow_data.json"

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
    "adaptive_timers_enabled": True
}

class MindFlowDB:
    def __init__(self):
        self.lock = threading.RLock()
        self.filepath = DB_FILE
        self.data = {
            "settings": DEFAULT_SETTINGS.copy(),
            "sessions": [],
            "reflections": []
        }
        self.load()

    def load(self):
        with self.lock:
            if os.path.exists(self.filepath):
                try:
                    with open(self.filepath, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        # Merge loaded keys to ensure schema safety
                        self.data["settings"] = {**DEFAULT_SETTINGS, **loaded.get("settings", {})}
                        self.data["sessions"] = loaded.get("sessions", [])
                        self.data["reflections"] = loaded.get("reflections", [])
                except Exception as e:
                    print(f"Error loading database, resetting to default: {e}")
                    self.save()
            else:
                self.save()

    def save(self):
        with self.lock:
            try:
                os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
                with open(self.filepath, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"Error saving database: {e}")

    def get_settings(self):
        return self.data["settings"]

    def update_settings(self, settings_dict):
        for k, v in settings_dict.items():
            if k in DEFAULT_SETTINGS:
                # Ensure type correctness
                if k in ["work_duration_minutes", "idle_timeout_seconds"]:
                    self.data["settings"][k] = int(v)
                elif k == "adaptive_timers_enabled":
                    self.data["settings"][k] = bool(v)
                elif isinstance(v, list):
                    # Filter, lowercase, and exclude generic browser names to prevent tracking hijacks
                    disallowed = {"chrome.exe", "chrome", "msedge.exe", "msedge", "firefox.exe", "firefox", "opera.exe", "opera", "brave.exe", "brave", "iexplore.exe", "iexplore", "browser", "explorer"}
                    self.data["settings"][k] = [
                        str(x).strip().lower() for x in v 
                        if x and str(x).strip().lower() not in disallowed
                    ]
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
            
            # Count bypasses today
            bypasses_today = 0
            today_date = datetime.today().date()
            for s in self.data.get("sessions", []):
                try:
                    start_dt = datetime.fromisoformat(s["start"])
                    if start_dt.date() == today_date and s.get("bypassed", False):
                        bypasses_today += 1
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
            base_rest_seconds = 20
            ref_rest_mod = 0
            if latest_refl:
                e = latest_refl.get("energy_level", 3)
                f = latest_refl.get("friction_level", 3)
                if e <= 2 or f >= 4:
                    ref_rest_mod = 10
            
            deficit_rest_mod = 10 * bypasses_today
            deficit_rest_mod = min(deficit_rest_mod, 30)
            
            total_rest_modifier = ref_rest_mod + deficit_rest_mod
            rest_seconds = min(60, base_rest_seconds + total_rest_modifier)
            
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

