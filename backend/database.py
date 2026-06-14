import os
import sys
import json
import re
import tempfile
import threading
import copy
import time
import math
import shutil
import sqlite3
from datetime import datetime

def get_default_data_dir():
    # 1. Determine standard target user-space directory
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if appdata:
            target_dir = os.path.join(appdata, "MIND")
        else:
            target_dir = os.path.join(os.path.expanduser("~"), ".mindflow")
    else:
        target_dir = os.path.join(os.path.expanduser("~"), ".mindflow")

    # 2. Check and auto-migrate from legacy C:\MIND path if needed
    legacy_dir = r"C:\MIND"
    if sys.platform == "win32" and os.path.exists(legacy_dir) and os.path.isdir(legacy_dir) and os.path.abspath(legacy_dir) != os.path.abspath(target_dir):
        try:
            # Check if there is anything to migrate before doing work
            migrate_items = ["mind_flow_data.db", "Workspace_Profiles", "mind_flow_data.json.bak"]
            has_migration_candidates = any(os.path.exists(os.path.join(legacy_dir, item)) for item in migrate_items)
            
            if has_migration_candidates:
                os.makedirs(target_dir, exist_ok=True)
                for item in migrate_items:
                    src = os.path.join(legacy_dir, item)
                    dst = os.path.join(target_dir, item)
                    if os.path.exists(src) and not os.path.exists(dst):
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)
        except Exception as e:
            # Fail silently to avoid breaking startup due to permissions
            print(f"[MIND-FLOW] Warning: Legacy data migration failed: {e}")

    return target_dir

DEFAULT_DATA_DIR = get_default_data_dir()
DB_FILE = os.getenv("MINDFLOW_DB_FILE", os.path.join(DEFAULT_DATA_DIR, "mind_flow_data.db"))

_keyword_regex_cache = {}
_combined_regex_cache = {}
_regex_lock = threading.Lock()
_simulated_disk = {}

def matches_any_keyword(keywords_list, text):
    """Check if any keyword in keywords_list matches a target text respecting word boundaries."""
    if not isinstance(text, str) or not keywords_list:
        return False
    
    # Convert list to tuple to make it hashable for the cache key
    cache_key = tuple(keywords_list)
    with _regex_lock:
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
    with _regex_lock:
        if kw not in _keyword_regex_cache:
            escaped_kw = re.escape(kw)
            left_boundary = r"(?<![a-zA-Z0-9])" if kw and kw[0].isalnum() else ""
            right_boundary = r"(?![a-zA-Z0-9])" if kw and kw[-1].isalnum() else ""
            pattern = f"{left_boundary}{escaped_kw}{right_boundary}"
            _keyword_regex_cache[kw] = re.compile(pattern)
        regex = _keyword_regex_cache[kw]
    return bool(regex.search(text))

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
    "circadian_forecast_sensitivity": "medium",
    "zen_level": "balanced",
    "daily_step_target": 10000,
    "daily_sleep_target": 8.0,
    "custom_rules": []
}

DEFAULT_CIRCADIAN_CURVE = {
    0: 1.5, 1: 1.2, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.2,
    6: 2.0, 7: 3.0, 8: 3.8, 9: 4.5, 10: 4.8, 11: 4.6,
    12: 3.8, 13: 3.2, 14: 3.0, 15: 3.6, 16: 4.0, 17: 4.2,
    18: 4.0, 19: 3.6, 20: 3.2, 21: 2.8, 22: 2.2, 23: 1.8
}

def is_browser_process(process):
    if not process:
        return False
    proc_lower = process.lower()
    browsers = {"chrome.exe", "chrome", "msedge.exe", "msedge", "firefox.exe", "firefox", 
                "opera.exe", "opera", "brave.exe", "brave", "safari.exe", "safari", 
                "vivaldi.exe", "vivaldi", "arc.exe", "arc", "orion.exe", "orion"}
    return proc_lower in browsers or any(b in proc_lower for b in ["browser", "iexplore"])

class FileLock:
    def __init__(self, lock_path, timeout=3.0, stale_age=10.0):
        self.lock_path = lock_path
        self.timeout = timeout
        self.stale_age = stale_age
        self.acquired = False

    def __enter__(self):
        start_time = time.time()
        while True:
            # Check for stale lock
            if os.path.exists(self.lock_path):
                try:
                    mtime = os.path.getmtime(self.lock_path)
                    if time.time() - mtime > self.stale_age:
                        try:
                            os.rmdir(self.lock_path)
                        except OSError:
                            pass
                except OSError:
                    pass
            
            try:
                os.mkdir(self.lock_path)
                self.acquired = True
                return self
            except FileExistsError:
                if time.time() - start_time > self.timeout:
                    raise TimeoutError(f"Could not acquire lock on {self.lock_path}: lock is held by another process")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.acquired:
            try:
                os.rmdir(self.lock_path)
            except OSError:
                pass
            self.acquired = False

class MindFlowDB:
    def __init__(self):
        self.lock = threading.RLock()
        self.filepath = DB_FILE
        self._thread_local = threading.local()
        self._master_conn = None
        self.app_usage_buffer = {}
        self.buffer_lock = threading.Lock()
        
        if self.filepath == ":memory:":
            # Instantiate a persistent master connection to maintain the shared memory database lifecycle
            self._master_conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
            
        self._init_db()
        self._migrate_legacy_json()
        
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

    def _get_conn(self):
        if self.filepath == ":memory:":
            conn = sqlite3.connect("file::memory:?cache=shared", uri=True, timeout=10.0)
        else:
            conn = sqlite3.connect(self.filepath, timeout=10.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass
        conn.row_factory = sqlite3.Row
        return conn

    from contextlib import contextmanager
    @contextmanager
    def connection(self):
        if not hasattr(self._thread_local, "conn") or self._thread_local.conn is None:
            self._thread_local.conn = self._get_conn()
        conn = self._thread_local.conn
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close(self):
        with self.lock:
            if hasattr(self._thread_local, "conn") and self._thread_local.conn is not None:
                try:
                    self._thread_local.conn.close()
                except Exception:
                    pass
                self._thread_local.conn = None
            if self._master_conn is not None:
                try:
                    self._master_conn.close()
                except Exception:
                    pass
                self._master_conn = None


    def _init_db(self):
        with self.connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT,
                    start TEXT,
                    end TEXT,
                    duration REAL,
                    brain_dump TEXT,
                    bypassed INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reflections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    energy_level INTEGER,
                    friction_level INTEGER,
                    summary TEXT,
                    mood TEXT,
                    sleep_hours REAL,
                    sleep_quality INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_usage (
                    date TEXT,
                    process TEXT,
                    title TEXT,
                    titles TEXT,
                    duration REAL,
                    PRIMARY KEY (date, process)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hydration (
                    date TEXT PRIMARY KEY,
                    cups REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS steps (
                    date TEXT PRIMARY KEY,
                    count INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sleep (
                    date TEXT PRIMARY KEY,
                    hours REAL,
                    quality INTEGER
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reflections_timestamp ON reflections(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_app_usage_date ON app_usage(date)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS battery_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    current_capacity REAL NOT NULL DEFAULT 100.0,
                    consecutive_work_minutes REAL NOT NULL DEFAULT 0.0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                INSERT OR IGNORE INTO battery_state (id, current_capacity, consecutive_work_minutes) 
                VALUES (1, 100.0, 0.0)
            """)
            
            cursor = conn.execute("SELECT COUNT(*) FROM settings")
            if cursor.fetchone()[0] == 0:
                for k, v in DEFAULT_SETTINGS.items():
                    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (k, json.dumps(v)))

    def _migrate_legacy_json(self):
        if self.filepath == ":memory:":
            return
        legacy_json_path = self.filepath.replace(".db", ".json")
        if os.path.exists(legacy_json_path) and os.path.isfile(legacy_json_path):
            with self.connection() as conn:
                row = conn.execute("SELECT value FROM metadata WHERE key = 'migrated_from_json'").fetchone()
                if row and row["value"] == "true":
                    return
            print(f"Legacy JSON database found at {legacy_json_path}. Migrating to SQLite...")
            try:
                with open(legacy_json_path, "r", encoding="utf-8") as f:
                    legacy_data = json.load(f)
                if not isinstance(legacy_data, dict):
                    legacy_data = {}
                with self.connection() as conn:
                    settings = legacy_data.get("settings", {})
                    for k, v in settings.items():
                        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, json.dumps(v)))
                    current_goal = legacy_data.get("current_goal", "")
                    if current_goal:
                        conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('current_goal', ?)", (current_goal,))
                    sessions = legacy_data.get("sessions", [])
                    if isinstance(sessions, list):
                        for s in sessions:
                            conn.execute("""
                                INSERT INTO sessions (mode, start, end, duration, brain_dump, bypassed)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                s.get("mode"),
                                s.get("start"),
                                s.get("end"),
                                s.get("duration"),
                                s.get("brain_dump"),
                                1 if s.get("bypassed") else 0
                            ))
                    reflections = legacy_data.get("reflections", [])
                    if isinstance(reflections, list):
                        for r in reflections:
                            conn.execute("""
                                INSERT INTO reflections (timestamp, energy_level, friction_level, summary, mood, sleep_hours, sleep_quality)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                r.get("timestamp"),
                                r.get("energy_level"),
                                r.get("friction_level"),
                                r.get("summary"),
                                r.get("mood"),
                                r.get("sleep_hours"),
                                r.get("sleep_quality")
                            ))
                    app_usage = legacy_data.get("app_usage", [])
                    if isinstance(app_usage, list):
                        for entry in app_usage:
                            date_str = entry.get("date")
                            process = entry.get("process")
                            if date_str and process:
                                titles_json = json.dumps(entry.get("titles", {}))
                                conn.execute("""
                                    INSERT OR REPLACE INTO app_usage (date, process, title, titles, duration)
                                    VALUES (?, ?, ?, ?, ?)
                                """, (
                                    date_str,
                                    process,
                                    entry.get("title"),
                                    titles_json,
                                    entry.get("duration")
                                ))
                    hydration = legacy_data.get("hydration", {})
                    if isinstance(hydration, dict) and hydration.get("date"):
                        conn.execute("INSERT OR REPLACE INTO hydration (date, cups) VALUES (?, ?)", (hydration["date"], hydration.get("cups", 0)))
                    steps = legacy_data.get("steps", [])
                    if isinstance(steps, list):
                        for st in steps:
                            date_str = st.get("date")
                            if date_str:
                                conn.execute("INSERT OR REPLACE INTO steps (date, count) VALUES (?, ?)", (date_str, st.get("count", 0)))
                    sleep = legacy_data.get("sleep", [])
                    if isinstance(sleep, list):
                        for sl in sleep:
                            date_str = sl.get("date")
                            if date_str:
                                conn.execute("INSERT OR REPLACE INTO sleep (date, hours, quality) VALUES (?, ?, ?)", (date_str, sl.get("hours", 0.0), sl.get("quality", 3)))
                    conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('migrated_from_json', 'true')")
                print("Migration to SQLite completed successfully.")
                backup_path = legacy_json_path + ".bak"
                try:
                    shutil.move(legacy_json_path, backup_path)
                    print(f"Backed up legacy JSON to {backup_path}")
                except Exception as e_mv:
                    print(f"Could not backup legacy JSON: {e_mv}")
            except Exception as e:
                print(f"Error migrating legacy JSON database: {e}")

    def load(self):
        if self.filepath == ":memory:":
            return
        if not os.path.exists(self.filepath):
            return
        conn = None
        try:
            conn = self._get_conn()
            conn.execute("SELECT COUNT(*) FROM settings")
        except Exception as e:
            backup_path = self.filepath + ".corrupt.bak"
            try:
                shutil.copy2(self.filepath, backup_path)
            except Exception:
                pass
            raise RuntimeError(f"Database file is corrupted: {e}")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


    def save(self, sync=False):
        self.flush_app_usage()

    def get_settings(self):
        with self.lock:
            settings = {}
            with self.connection() as conn:
                for row in conn.execute("SELECT key, value FROM settings"):
                    settings[row["key"]] = json.loads(row["value"])
            for k, v in DEFAULT_SETTINGS.items():
                if k not in settings:
                    settings[k] = copy.deepcopy(v)
            return settings

    def get_current_goal(self):
        with self.lock:
            with self.connection() as conn:
                row = conn.execute("SELECT value FROM metadata WHERE key = 'current_goal'").fetchone()
                return row["value"] if row else ""

    def set_current_goal(self, goal):
        with self.lock:
            with self.connection() as conn:
                conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('current_goal', ?)", (str(goal).strip(),))

    def get_hydration(self):
        with self.lock:
            today_str = datetime.today().date().isoformat()
            with self.connection() as conn:
                row = conn.execute("SELECT cups FROM hydration WHERE date = ?", (today_str,)).fetchone()
                if not row:
                    cups = 0.0
                else:
                    cups = row["cups"]
            settings = self.get_settings()
            return {
                "date": today_str,
                "cups": cups,
                "target": settings.get("hydration_target", 8),
                "unit": settings.get("hydration_unit", "cups"),
                "increment": settings.get("hydration_increment", 1)
            }

    def increment_hydration(self, cups=None):
        with self.lock:
            today_str = datetime.today().date().isoformat()
            settings = self.get_settings()
            with self.connection() as conn:
                row = conn.execute("SELECT cups FROM hydration WHERE date = ?", (today_str,)).fetchone()
                current_cups = row["cups"] if row else 0.0
                if cups is not None:
                    try:
                        val = float(cups)
                        if val.is_integer():
                            val = int(val)
                        new_cups = max(0.0, min(10000.0, val))
                    except (ValueError, TypeError):
                        new_cups = current_cups
                else:
                    inc = settings.get("hydration_increment", 1)
                    try:
                        val = float(current_cups) + float(inc)
                        if val.is_integer():
                            val = int(val)
                        new_cups = min(10000.0, val)
                    except (ValueError, TypeError):
                        new_cups = current_cups
                conn.execute("INSERT OR REPLACE INTO hydration (date, cups) VALUES (?, ?)", (today_str, new_cups))
            return {
                "date": today_str,
                "cups": new_cups,
                "target": settings.get("hydration_target", 8),
                "unit": settings.get("hydration_unit", "cups"),
                "increment": settings.get("hydration_increment", 1)
            }

    def get_steps(self, date_str=None):
        with self.lock:
            if not date_str:
                date_str = datetime.today().date().isoformat()
            with self.connection() as conn:
                row = conn.execute("SELECT count FROM steps WHERE date = ?", (date_str,)).fetchone()
                return row["count"] if row else 0

    def log_steps(self, count, date_str=None):
        with self.lock:
            if not date_str:
                date_str = datetime.today().date().isoformat()
            try:
                count_val = int(count)
            except (ValueError, TypeError):
                count_val = 0
            with self.connection() as conn:
                conn.execute("INSERT OR REPLACE INTO steps (date, count) VALUES (?, ?)", (date_str, count_val))
            return count_val

    def get_sleep(self, date_str=None):
        with self.lock:
            if not date_str:
                date_str = datetime.today().date().isoformat()
            with self.connection() as conn:
                row = conn.execute("SELECT hours, quality FROM sleep WHERE date = ?", (date_str,)).fetchone()
                if row:
                    return {
                        "hours": row["hours"],
                        "quality": row["quality"]
                    }
                return {"hours": 0.0, "quality": 3}

    def log_sleep(self, hours, quality, date_str=None):
        with self.lock:
            if not date_str:
                date_str = datetime.today().date().isoformat()
            try:
                hours_val = float(hours)
            except (ValueError, TypeError):
                hours_val = 0.0
            try:
                quality_val = int(quality)
            except (ValueError, TypeError):
                quality_val = 3
            with self.connection() as conn:
                conn.execute("INSERT OR REPLACE INTO sleep (date, hours, quality) VALUES (?, ?, ?)", (date_str, hours_val, quality_val))
            return {"hours": hours_val, "quality": quality_val}

    def get_sleep_list(self):
        with self.lock:
            sleep = []
            with self.connection() as conn:
                for row in conn.execute("SELECT date, hours, quality FROM sleep ORDER BY date ASC"):
                    sleep.append({
                        "date": row["date"],
                        "hours": row["hours"],
                        "quality": row["quality"]
                    })
            return sleep

    def get_steps_list(self):
        with self.lock:
            steps = []
            with self.connection() as conn:
                for row in conn.execute("SELECT date, count FROM steps ORDER BY date ASC"):
                    steps.append({
                        "date": row["date"],
                        "count": row["count"]
                    })
            return steps

    def update_settings(self, settings_dict):
        with self.lock:
            settings = self.get_settings()
            for k, v in settings_dict.items():
                if k in DEFAULT_SETTINGS:
                    if k in ["work_duration_minutes", "idle_timeout_seconds", "rest_duration_seconds"]:
                        try:
                            val = int(v)
                            if k == "work_duration_minutes":
                                val = max(10, min(180, val))
                            elif k == "idle_timeout_seconds":
                                val = max(10, min(3600, val))
                            elif k == "rest_duration_seconds":
                                val = max(5, min(600, val))
                            settings[k] = val
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
                            settings[k] = val
                        except (ValueError, TypeError):
                            pass
                    elif k == "hydration_unit":
                        val = str(v).strip().lower()
                        if val in ["cups", "ml", "oz"]:
                            settings[k] = val
                    elif k in ["adaptive_timers_enabled", "eye_care_mode", "circadian_forecast_enabled"]:
                        if isinstance(v, str):
                            settings[k] = v.lower() in ["true", "1", "yes"]
                        else:
                            settings[k] = bool(v)
                    elif k == "circadian_forecast_sensitivity":
                        val = str(v).strip().lower()
                        if val in ["low", "medium", "high"]:
                            settings[k] = val
                    elif k == "zen_level":
                        val = str(v).strip().lower()
                        if val in ["tranquil", "balanced", "sprint"]:
                            settings[k] = val
                    elif k == "daily_step_target":
                        try:
                            val = int(v)
                            settings[k] = max(1, min(1000000, val))
                        except (ValueError, TypeError):
                            pass
                    elif k == "daily_sleep_target":
                        try:
                            val = float(v)
                            settings[k] = max(1.0, min(24.0, val))
                        except (ValueError, TypeError):
                            pass
                    elif k == "custom_rules" and isinstance(v, list):
                        rules = []
                        for r in v:
                            if isinstance(r, dict) and "pattern" in r and "category" in r:
                                rules.append({
                                    "pattern": str(r["pattern"]).strip(),
                                    "category": str(r["category"]).strip().lower()
                                })
                        settings[k] = rules[:50]
                    elif isinstance(v, list):
                        filtered = [str(x).strip().lower() for x in v if x]
                        settings[k] = filtered[:50]
            with self.connection() as conn:
                for k, v in settings.items():
                    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, json.dumps(v)))

    def log_session(self, mode, start_time, end_time, brain_dump=None, bypassed=False):
        duration = (end_time - start_time).total_seconds()
        if duration < 5:
            return
        with self.lock:
            with self.connection() as conn:
                conn.execute("""
                    INSERT INTO sessions (mode, start, end, duration, brain_dump, bypassed)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (mode, start_time.isoformat(), end_time.isoformat(), duration, brain_dump, 1 if bypassed else 0))

    def add_reflection(self, energy_level, friction_level, summary, mood=None, sleep_hours=None, sleep_quality=None):
        try:
            val = float(energy_level)
            energy_val = int(val) if val.is_integer() else round(val, 2)
        except (ValueError, TypeError):
            energy_val = 3
        try:
            val = float(friction_level)
            friction_val = int(val) if val.is_integer() else round(val, 2)
        except (ValueError, TypeError):
            friction_val = 3
        try:
            sleep_hours_val = float(sleep_hours) if sleep_hours is not None else None
        except (ValueError, TypeError):
            sleep_hours_val = None
        try:
            sleep_quality_val = int(sleep_quality) if sleep_quality is not None else None
        except (ValueError, TypeError):
            sleep_quality_val = None
        with self.lock:
            timestamp = datetime.now().isoformat()
            with self.connection() as conn:
                conn.execute("""
                    INSERT INTO reflections (timestamp, energy_level, friction_level, summary, mood, sleep_hours, sleep_quality)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, energy_val, friction_val, str(summary).strip(), str(mood).strip() if mood else None, sleep_hours_val, sleep_quality_val))
            return {
                "timestamp": timestamp,
                "energy_level": energy_val,
                "friction_level": friction_val,
                "summary": str(summary).strip(),
                "mood": str(mood).strip() if mood else None,
                "sleep_hours": sleep_hours_val,
                "sleep_quality": sleep_quality_val
            }

    def get_reflections(self):
        with self.lock:
            reflections = []
            with self.connection() as conn:
                for row in conn.execute("SELECT timestamp, energy_level, friction_level, summary, mood, sleep_hours, sleep_quality FROM reflections ORDER BY id ASC"):
                    reflections.append({
                        "timestamp": row["timestamp"],
                        "energy_level": row["energy_level"],
                        "friction_level": row["friction_level"],
                        "summary": row["summary"],
                        "mood": row["mood"],
                        "sleep_hours": row["sleep_hours"],
                        "sleep_quality": row["sleep_quality"]
                    })
            return reflections

    def get_sessions(self):
        with self.lock:
            sessions = []
            with self.connection() as conn:
                for row in conn.execute("SELECT mode, start, end, duration, brain_dump, bypassed FROM sessions ORDER BY id ASC"):
                    sessions.append({
                        "mode": row["mode"],
                        "start": row["start"],
                        "end": row["end"],
                        "duration": row["duration"],
                        "brain_dump": row["brain_dump"],
                        "bypassed": bool(row["bypassed"])
                    })
            return sessions

    def log_app_usage(self, process, title, duration):
        if not process or process == "None":
            return
        with self.buffer_lock:
            key = (process, title)
            self.app_usage_buffer[key] = self.app_usage_buffer.get(key, 0) + duration

    def flush_app_usage(self):
        with self.buffer_lock:
            if not self.app_usage_buffer:
                return
            today_str = datetime.today().date().isoformat()
            with self.lock:
                with self.connection() as conn:
                    for (process, title), duration in self.app_usage_buffer.items():
                        row = conn.execute("SELECT titles, duration FROM app_usage WHERE date = ? AND process = ?", (today_str, process)).fetchone()
                        if row:
                            titles = json.loads(row["titles"]) if row["titles"] else {}
                            new_duration = row["duration"] + duration
                            if title and title != "None":
                                titles[title] = titles.get(title, 0) + duration
                            conn.execute("""
                                UPDATE app_usage 
                                SET title = ?, titles = ?, duration = ?
                                WHERE date = ? AND process = ?
                            """, (title if title else "None", json.dumps(titles), new_duration, today_str, process))
                        else:
                            titles = {}
                            if title and title != "None":
                                titles[title] = duration
                            conn.execute("""
                                INSERT INTO app_usage (date, process, title, titles, duration)
                                VALUES (?, ?, ?, ?, ?)
                            """, (today_str, process, title if title else "None", json.dumps(titles), duration))
                    self.app_usage_buffer.clear()

    def get_app_usage(self):
        self.flush_app_usage()
        with self.lock:
            usage = []
            with self.connection() as conn:
                for row in conn.execute("SELECT date, process, title, titles, duration FROM app_usage ORDER BY rowid ASC"):
                    usage.append({
                        "date": row["date"],
                        "process": row["process"],
                        "title": row["title"],
                        "titles": json.loads(row["titles"]) if row["titles"] else {},
                        "duration": row["duration"]
                    })
            return usage

    def _get_hydration_context(self, now=None):
        if now is None:
            now = datetime.now()
        today_date = now.date()
        today_str = today_date.isoformat()
        with self.connection() as conn:
            row = conn.execute("SELECT cups FROM hydration WHERE date = ?", (today_str,)).fetchone()
            
        has_logged_today = (row is not None)
        cups = row["cups"] if has_logged_today else 0.0

        # Fallback to 7-day average if today has no hydration logged
        fallback_active = False
        if not has_logged_today:
            from datetime import timedelta
            try:
                with self.connection() as conn:
                    # Query 7 days prior to today
                    cursor_hist = conn.execute("""
                        SELECT cups FROM hydration 
                        WHERE date != ? AND date >= ?
                        ORDER BY date DESC LIMIT 7
                    """, (today_str, (today_date - timedelta(days=7)).isoformat()))
                    hist_rows = cursor_hist.fetchall()
                    if hist_rows:
                        avg_cups = sum(r["cups"] for r in hist_rows) / len(hist_rows)
                        if avg_cups > 0.0:
                            cups = avg_cups
                            fallback_active = True
            except Exception:
                pass

        settings = self.get_settings()
        target = settings.get("hydration_target", 8)
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
                if has_logged_today or fallback_active:
                    modifier = -0.30
                else:
                    modifier = 0.0
        return {
            "cups": cups if not fallback_active else 0.0,
            "target": target,
            "expected_amount": expected_amount,
            "ratio": ratio,
            "modifier": modifier
        }

    def get_circadian_forecast(self):
        from datetime import timedelta
        now = datetime.now()
        today_date = now.date()
        today_str = today_date.isoformat()
        thirty_days_ago = (today_date - timedelta(days=30)).isoformat()
        sleep_hours = None
        sleep_quality = None
        sleep_modifier = 0.0
        with self.connection() as conn:
            row_sleep = conn.execute("""
                SELECT sleep_hours, sleep_quality 
                FROM reflections 
                WHERE timestamp LIKE ? AND (sleep_hours IS NOT NULL OR sleep_quality IS NOT NULL)
                ORDER BY id DESC LIMIT 1
            """, (today_str + "%",)).fetchone()
            if row_sleep:
                sleep_hours = row_sleep["sleep_hours"]
                sleep_quality = row_sleep["sleep_quality"]
            
            if sleep_hours is None and sleep_quality is None:
                try:
                    cursor_sleep_hist = conn.execute("""
                        SELECT sleep_hours, sleep_quality 
                        FROM reflections 
                        WHERE timestamp < ? AND (sleep_hours IS NOT NULL OR sleep_quality IS NOT NULL)
                        ORDER BY id DESC LIMIT 7
                    """, (today_str,))
                    sleep_rows = cursor_sleep_hist.fetchall()
                    if sleep_rows:
                        valid_hours = [r["sleep_hours"] for r in sleep_rows if r["sleep_hours"] is not None]
                        valid_qualities = [r["sleep_quality"] for r in sleep_rows if r["sleep_quality"] is not None]
                        if valid_hours:
                            sleep_hours = sum(valid_hours) / len(valid_hours)
                        if valid_qualities:
                            sleep_quality = int(sum(valid_qualities) / len(valid_qualities))
                except Exception:
                    pass
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
                sleep_modifier = max(-1.5, min(0.5, sleep_modifier))
            hourly_ratings = {i: [] for i in range(24)}
            cursor = conn.execute("""
                SELECT timestamp, energy_level 
                FROM reflections 
                WHERE timestamp >= ? AND timestamp <= ?
            """, (thirty_days_ago, now.isoformat()))
            for r in cursor:
                try:
                    r_dt = datetime.fromisoformat(r["timestamp"])
                    if r_dt.tzinfo is not None:
                        r_dt = r_dt.replace(tzinfo=None)
                    h = r_dt.hour
                    hourly_ratings[h].append(r["energy_level"])
                except Exception:
                    pass
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
                w = min(1.0, cnt / 3.0)
                predicted_energy = w * avg_historical + (1.0 - w) * def_val
            else:
                predicted_energy = def_val
            predicted_energy = max(1.0, min(5.0, predicted_energy + total_modifier))
            forecast_curve.append({
                "hour": h,
                "energy": round(predicted_energy, 2)
            })
        def energy_at_hour(hour_val):
            h_floor = int(math.floor(hour_val)) % 24
            h_ceil = (h_floor + 1) % 24
            fraction = hour_val - math.floor(hour_val)
            val_floor = forecast_curve[h_floor]["energy"]
            val_ceil = forecast_curve[h_ceil]["energy"]
            return val_floor * (1.0 - fraction) + val_ceil * fraction
        settings = self.get_settings()
        enabled = settings.get("circadian_forecast_enabled", True)
        sensitivity = settings.get("circadian_forecast_sensitivity", "medium")
        if sensitivity == "low":
            drop_threshold = 0.8
            low_threshold = 2.5
        elif sensitivity == "high":
            drop_threshold = 0.3
            low_threshold = 3.6
        else:
            drop_threshold = 0.5
            low_threshold = 3.2
        impending_drop = False
        slump_minutes = 0
        lowest_future_energy = 5.0
        current_hour_val = now.hour + now.minute / 60.0
        current_energy = energy_at_hour(current_hour_val)
        def baseline_energy_at_hour(hour_val):
            h_floor = int(math.floor(hour_val)) % 24
            h_ceil = (h_floor + 1) % 24
            fraction = hour_val - math.floor(hour_val)
            val_floor = DEFAULT_CIRCADIAN_CURVE[h_floor]
            val_ceil = DEFAULT_CIRCADIAN_CURVE[h_ceil]
            return val_floor * (1.0 - fraction) + val_ceil * fraction
        if enabled:
            for offset_mins in range(15, 105, 15):
                future_hour_val = (current_hour_val + offset_mins / 60.0) % 24
                future_energy = energy_at_hour(future_hour_val)
                drop = current_energy - future_energy
                is_evening_wind_down = (current_hour_val >= 19.0 or current_hour_val < 6.0)
                if is_evening_wind_down:
                    baseline_curr = baseline_energy_at_hour(current_hour_val)
                    baseline_fut = baseline_energy_at_hour(future_hour_val)
                    baseline_drop = baseline_curr - baseline_fut
                    is_slump = (drop - baseline_drop) >= drop_threshold
                else:
                    is_slump = (drop >= drop_threshold or future_energy <= low_threshold)
                if is_slump and future_energy < current_energy:
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
        from datetime import timedelta
        today_date = datetime.today().date()
        today_str = today_date.isoformat()
        with self.connection() as conn:
            sessions_cnt = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            reflections_cnt = conn.execute("SELECT COUNT(*) FROM reflections").fetchone()[0]
        settings = self.get_settings()
        now_time = time.time()
        cache = self._adaptive_cache
        if (cache["result"] is not None and
            cache["last_settings"] == settings and
            cache["last_sessions_len"] == sessions_cnt and
            cache["last_reflections_len"] == reflections_cnt and
            cache["last_checked_date"] == today_date and
            (now_time - cache["last_check_time"]) < 10.0):
            return cache["result"]
        zen_lvl = settings.get("zen_level", "balanced")
        if zen_lvl == "tranquil":
            base_work_minutes = 35
            base_rest_seconds = 30
        elif zen_lvl == "sprint":
            base_work_minutes = 55
            base_rest_seconds = 15
        else:
            base_work_minutes = settings.get("work_duration_minutes", 45)
            base_rest_seconds = settings.get("rest_duration_seconds", 20)
        if not settings.get("adaptive_timers_enabled", True):
            result = {
                "work_minutes": base_work_minutes,
                "work_modifier": 0,
                "rest_seconds": base_rest_seconds,
                "rest_modifier": 0,
                "reason": "Autopilot Off"
            }
            cache["last_settings"] = settings
            cache["last_sessions_len"] = sessions_cnt
            cache["last_reflections_len"] = reflections_cnt
            cache["last_checked_date"] = today_date
            cache["last_check_time"] = now_time
            cache["result"] = result
            return result
        with self.connection() as conn:
            rows_sessions = conn.execute("""
                SELECT mode, bypassed 
                FROM sessions 
                WHERE start LIKE ? 
                ORDER BY start ASC
            """, (today_str + "%",)).fetchall()
        bypasses_today = 0
        for s in rows_sessions:
            if s["mode"] in ["rest", "recharge"] and not s["bypassed"]:
                bypasses_today = max(0, bypasses_today - 1)
            elif s["bypassed"]:
                bypasses_today += 1
        three_hours_ago = (datetime.now() - timedelta(hours=3)).isoformat()
        with self.connection() as conn:
            row_refl = conn.execute("""
                SELECT energy_level, friction_level 
                FROM reflections 
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY id DESC LIMIT 1
            """, (three_hours_ago, datetime.now().isoformat())).fetchone()
        ref_work_mod = 0
        latest_refl = row_refl
        if latest_refl:
            e = latest_refl["energy_level"]
            f = latest_refl["friction_level"]
            if e >= 4 and f <= 2:
                ref_work_mod = (e - 3) * 5 + (3 - f) * 5
                ref_work_mod = min(ref_work_mod, 15)
            elif e <= 2 or f >= 4:
                ref_work_mod = -((3 - e) * 5 + (f - 3) * 5)
                ref_work_mod = max(ref_work_mod, -15)
        bypass_work_mod = -5 * bypasses_today
        bypass_work_mod = max(bypass_work_mod, -10)
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
                else:
                    forecast_adjusted_work = -10
                    forecast_adjusted_rest = 15
        hydration_work_mod = 0
        hydration_rest_mod = 0
        hyd_ctx = self._get_hydration_context(datetime.now())
        if datetime.now().hour >= 10 and hyd_ctx["ratio"] < 0.5:
            hydration_work_mod = -5
            hydration_rest_mod = 15
        total_work_modifier = ref_work_mod + bypass_work_mod + forecast_adjusted_work + hydration_work_mod
        work_minutes = max(10, min(90, base_work_minutes + total_work_modifier))
        zen_lvl = settings.get("zen_level", "balanced")
        if zen_lvl == "tranquil":
            base_rest_seconds = 30
        elif zen_lvl == "sprint":
            base_rest_seconds = 15
        else:
            base_rest_seconds = settings.get("rest_duration_seconds", 20)
        ref_rest_mod = 0
        if latest_refl:
            e = latest_refl["energy_level"]
            f = latest_refl["friction_level"]
            if e <= 2 or f >= 4:
                ref_rest_mod = 10
        deficit_rest_mod = 10 * bypasses_today
        deficit_rest_mod = min(deficit_rest_mod, 20)
        with self.connection() as conn:
            rows_friction = conn.execute("""
                SELECT friction_level 
                FROM reflections 
                WHERE timestamp LIKE ? AND summary NOT LIKE '[Autopilot]%'
            """, (today_str + "%",)).fetchall()
        avg_friction = sum(r["friction_level"] for r in rows_friction) / len(rows_friction) if rows_friction else 1.0
        friction_rest_mod = 0
        if avg_friction >= 3.0:
            friction_rest_mod = int((avg_friction - 2.0) * 8)
            friction_rest_mod = min(25, friction_rest_mod)
        total_rest_modifier = ref_rest_mod + deficit_rest_mod + friction_rest_mod + forecast_adjusted_rest + hydration_rest_mod
        rest_seconds = min(600, base_rest_seconds + total_rest_modifier)
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
        cache["last_sessions_len"] = sessions_cnt
        cache["last_reflections_len"] = reflections_cnt
        cache["last_checked_date"] = today_date
        cache["last_check_time"] = now_time
        cache["result"] = result
        return result

    def get_cached_status_data(self):
        from datetime import date
        today_date = datetime.today().date()
        today_str = today_date.isoformat()
        now_time = time.time()
        with self.connection() as conn:
            sessions_cnt = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            reflections_cnt = conn.execute("SELECT COUNT(*) FROM reflections").fetchone()[0]
        cache = self._status_cache
        if (cache["result"] is not None and
            cache["last_sessions_len"] == sessions_cnt and
            cache["last_reflections_len"] == reflections_cnt and
            cache["last_checked_date"] == today_date and
            (now_time - cache.get("last_check_time", 0.0)) < 10.0):
            return cache["result"]
        with self.connection() as conn:
            row_energy = conn.execute("""
                SELECT energy_level 
                FROM reflections 
                WHERE timestamp LIKE ? 
                ORDER BY id DESC LIMIT 1
            """, (today_str + "%",)).fetchone()
            current_energy = row_energy["energy_level"] if row_energy else 5
            rows_stress = conn.execute("""
                SELECT energy_level, friction_level, mood 
                FROM reflections 
                WHERE summary NOT LIKE '[Autopilot]%'
                ORDER BY id DESC LIMIT 2
            """).fetchall()
            high_stress_alert = False
            latest_mood = None
            if len(rows_stress) >= 1:
                latest_mood = rows_stress[0]["mood"]
                if len(rows_stress) == 2:
                    stress_flags = []
                    for ur in rows_stress:
                        e = ur["energy_level"]
                        f = ur["friction_level"]
                        if e <= 2 or f >= 4:
                            stress_flags.append(True)
                        else:
                            stress_flags.append(False)
                    if all(stress_flags):
                        high_stress_alert = True
            row_sess_sum = conn.execute("""
                SELECT 
                    SUM(CASE WHEN mode = 'work' THEN duration ELSE 0 END) as work_sec,
                    SUM(CASE WHEN mode = 'recharge' THEN duration ELSE 0 END) as recharge_sec,
                    SUM(CASE WHEN mode = 'rest' THEN duration ELSE 0 END) as rest_sec,
                    SUM(CASE WHEN bypassed = 1 THEN 1 ELSE 0 END) as bypasses_cnt
                FROM sessions 
                WHERE start LIKE ?
            """, (today_str + "%",)).fetchone()
            today_work_seconds = row_sess_sum["work_sec"] or 0.0
            today_recharge_seconds = row_sess_sum["recharge_sec"] or 0.0
            today_rest_seconds = row_sess_sum["rest_sec"] or 0.0
            today_bypasses = row_sess_sum["bypasses_cnt"] or 0
            forecast_fatigue_alert = ""
            try:
                from collections import defaultdict
                from datetime import timedelta
                reflections_by_date = defaultdict(list)
                thirty_days_ago = today_date - timedelta(days=30)
                cursor_ref = conn.execute("""
                    SELECT timestamp, energy_level 
                    FROM reflections 
                    WHERE timestamp >= ? AND timestamp < ?
                """, (thirty_days_ago.isoformat(), today_str))
                for r in cursor_ref:
                    try:
                        r_dt = datetime.fromisoformat(r["timestamp"])
                        r_date = r_dt.date()
                        reflections_by_date[r_date].append(r["energy_level"])
                    except Exception:
                        pass
                if reflections_by_date:
                    avg_past_daily_energy = sum(sum(levels)/len(levels) for levels in reflections_by_date.values()) / len(reflections_by_date)
                    cursor_today = conn.execute("""
                        SELECT energy_level 
                        FROM reflections 
                        WHERE timestamp LIKE ?
                    """, (today_str + "%",))
                    today_levels = [r["energy_level"] for r in cursor_today]
                    if today_levels:
                        today_avg = sum(today_levels) / len(today_levels)
                        if today_avg < avg_past_daily_energy - 0.5:
                            forecast_fatigue_alert = " (Accumulated fatigue alert: Energy is running lower than your historic average)"
            except Exception:
                pass
        forecast = self.get_circadian_forecast()
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
        cache["last_sessions_len"] = sessions_cnt
        cache["last_reflections_len"] = reflections_cnt
        cache["last_checked_date"] = today_date
        cache["last_check_time"] = now_time
        cache["result"] = result
        return result

    def get_battery_state(self) -> dict:
        with self.lock:
            with self.connection() as conn:
                row = conn.execute(
                    "SELECT current_capacity, consecutive_work_minutes FROM battery_state WHERE id = 1"
                ).fetchone()
                return {"capacity": row[0], "consecutive_work": row[1]}

    def flush_battery_state(self, capacity: float, consecutive_work: float):
        with self.lock:
            with self.connection() as conn:
                conn.execute("""
                    UPDATE battery_state
                    SET current_capacity = ?, consecutive_work_minutes = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE id = 1
                """, (capacity, consecutive_work))


