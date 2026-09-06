"""
Database abstraction layer for MIND-FLOW providing SQLite WAL-mode concurrency,
session tracking, analytics persistence, and schema migrations.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import json
import re
import tempfile
import threading
import queue
import concurrent.futures
import functools
import copy
import time
import math
import shutil
import sqlite3
import logging
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

import threading
_regex_lock = threading.RLock()
_REGEX_CACHE_MAX_SIZE = 250
_keyword_regex_cache = {}
_combined_regex_cache = {}

def matches_any_keyword(keywords_list, text):
    """Check if any keyword in keywords_list matches a target text respecting word boundaries."""
    if not isinstance(text, str) or not keywords_list:
        return False
    
    # Convert list to tuple to make it hashable for the cache key
    cache_key = tuple(keywords_list)
    with _regex_lock:
        regex = _combined_regex_cache.get(cache_key, "NOT_FOUND")
        
    if regex == "NOT_FOUND":
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
        compiled = re.compile("|".join(patterns)) if patterns else None
        with _regex_lock:
            if len(_combined_regex_cache) >= _REGEX_CACHE_MAX_SIZE:
                _combined_regex_cache.clear()
            _combined_regex_cache[cache_key] = compiled
            regex = compiled
            
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
        regex = _keyword_regex_cache.get(kw, "NOT_FOUND")
        
    if regex == "NOT_FOUND":
        escaped_kw = re.escape(kw)
        left_boundary = r"(?<![a-zA-Z0-9])" if kw and kw[0].isalnum() else ""
        right_boundary = r"(?![a-zA-Z0-9])" if kw and kw[-1].isalnum() else ""
        pattern = f"{left_boundary}{escaped_kw}{right_boundary}"
        compiled = re.compile(pattern)
        with _regex_lock:
            if len(_keyword_regex_cache) >= _REGEX_CACHE_MAX_SIZE:
                _keyword_regex_cache.clear()
            _keyword_regex_cache[kw] = compiled
            regex = compiled
            
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
    "neutral_keywords": [],
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
    "custom_rules": [],
    "proactivity_level": "balanced",
    "enable_desktop_toasts": True,
    "enable_audio_chimes": True,
    "enable_distraction_nudges": True,
    "enable_thrashing_nudges": True,
    "enable_hydration_nudges": True,
    "enable_eyecare_nudges": True,
    "nudge_cooldown_minutes": 5
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

from backend.task_classifier import is_safe_regex

_cache_invalidation_listeners = []

def register_cache_invalidation_listener(callback):
    """Register a callback to be invoked when settings change and caches need invalidation."""
    if callback not in _cache_invalidation_listeners:
        _cache_invalidation_listeners.append(callback)

def clear_regex_caches():
    """Clear all global compiled regex caches in database and notify registered listeners."""
    with _regex_lock:
        _keyword_regex_cache.clear()
        _combined_regex_cache.clear()
    for listener in list(_cache_invalidation_listeners):
        try:
            listener()
        except Exception:
            pass
    try:
        from backend.task_classifier import TaskClassifier
        TaskClassifier.clear_cache()
    except Exception:
        pass

def clear_analytics_cache():
    """Module-level function to clear in-memory analytics cache in server module."""
    try:
        from backend.server import _analytics_cache, _analytics_cache_lock
        with _analytics_cache_lock:
            _analytics_cache.clear()
    except Exception:
        pass

def _get_db_worker_logger():
    logger = logging.getLogger("db_worker")
    if not logger.handlers:
        log_path = os.path.join(DEFAULT_DATA_DIR, "db_worker.log")
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s'))
        logger.addHandler(fh)
        logger.setLevel(logging.WARNING)
    return logger

def _handle_async_future_exception(fut):
    try:
        exc = fut.exception()
        if exc:
            logger = _get_db_worker_logger()
            logger.error(f"[ASYNC_FUTURE_EXCEPTION] Un-awaited DB write failed: {exc}", exc_info=exc)
    except Exception:
        pass

_worker_spawn_lock = threading.Lock()

def queued_write(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if getattr(self._thread_local, "is_worker", False):
            return func(self, *args, **kwargs)
        wait = kwargs.pop("wait", True)
        future = concurrent.futures.Future()
        if not hasattr(self, "_db_worker_thread") or not self._db_worker_thread.is_alive():
            with _worker_spawn_lock:
                if not hasattr(self, "_db_worker_thread") or not self._db_worker_thread.is_alive():
                    self._db_worker_thread = threading.Thread(target=self._db_worker, daemon=True, name="DBWriteWorker")
                    self._db_worker_thread.start()
        if wait:
            try:
                self._write_queue.put((func, self, args, kwargs, future), block=True, timeout=5.0)
            except queue.Full:
                _get_db_worker_logger().error(f"[DB_QUEUE_FULL] Blocking DB task '{func.__name__}' timed out waiting for queue slot.")
                raise queue.Full(f"DB write queue capacity reached (maxsize=1000) for task '{func.__name__}'")
            return future.result()
        else:
            try:
                self._write_queue.put_nowait((func, self, args, kwargs, future))
            except queue.Full:
                _get_db_worker_logger().warning(f"[DB_QUEUE_FULL] Dropping non-blocking DB task '{func.__name__}' due to queue capacity (maxsize=1000).")
                future.set_exception(queue.Full("DB write queue capacity reached (maxsize=1000)"))
                return future
            future.add_done_callback(_handle_async_future_exception)
            return future
    return wrapper

class MindFlowDB:
    _settings_cache = None
    _settings_lock = threading.RLock()

    def __init__(self, db_path=None):
        self.filepath = db_path if db_path else DB_FILE
        self._thread_local = threading.local()
        self._master_conn = None
        self.app_usage_buffer = {}
        self.buffer_lock = threading.RLock()
        self.write_counter = 0
        self.analytics_write_counter = 0
        
        self._write_queue = queue.Queue(maxsize=1000)
        self._db_worker_thread = threading.Thread(target=self._db_worker, daemon=True, name="DBWriteWorker")
        self._db_worker_thread.start()
        
        self._adaptive_cache = {
            "last_settings": None,
            "last_write_counter": -1,
            "last_checked_date": None,
            "last_check_time": 0.0,
            "result": None
        }
        self._streak_cache = {
            "last_write_counter": -1,
            "last_checked_date": None,
            "last_check_time": 0.0,
            "result": None
        }
        self._recovery_cache = {
            "last_write_counter": -1,
            "last_checked_date": None,
            "last_check_time": 0.0,
            "result": None
        }
        self._status_cache = {
            "last_write_counter": -1,
            "last_checked_date": None,
            "last_check_time": 0.0,
            "result": None
        }
        self._achievements_cache = {
            "last_write_counter": -1,
            "last_check_time": 0.0,
            "result": None
        }

        if self.filepath == ":memory:":
            # Instantiate a persistent master connection to maintain the shared memory database lifecycle
            self._master_conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
            
        self._init_db()
        self._migrate_legacy_json()
        self._merge_legacy_db()

        from backend.columnar_analytics import ColumnarAnalyticsEngine
        duckdb_path = ":memory:" if self.filepath == ":memory:" else None
        self.columnar_engine = ColumnarAnalyticsEngine(db_path=duckdb_path, sqlite_db=self)

    def clear_analytics_cache(self):
        """Invalidate all internal database analytics caches and server response caches."""
        self.analytics_write_counter += 1
        if hasattr(self, "_adaptive_cache"):
            self._adaptive_cache["last_write_counter"] = -1
        if hasattr(self, "_streak_cache"):
            self._streak_cache["last_write_counter"] = -1
        if hasattr(self, "_recovery_cache"):
            self._recovery_cache["last_write_counter"] = -1
        if hasattr(self, "_status_cache"):
            self._status_cache["last_write_counter"] = -1
        if hasattr(self, "_achievements_cache"):
            self._achievements_cache["last_write_counter"] = -1
        clear_analytics_cache()

    def _db_worker(self):
        self._thread_local.is_worker = True
        logger = _get_db_worker_logger()
        while True:
            try:
                task = self._write_queue.get()
                if task is None:
                    self._write_queue.task_done()
                    if self._write_queue.empty():
                        break
                    continue
                func, obj, args, kwargs, future = task
                try:
                    res = None
                    executed_successfully = False
                    max_retries = 3
                    initial_delay = 0.05

                    for attempt in range(max_retries + 1):
                        try:
                            res = func(obj, *args, **kwargs)
                            executed_successfully = True
                            break
                        except sqlite3.OperationalError as e:
                            is_transient = "locked" in str(e).lower() or "busy" in str(e).lower()
                            if is_transient and attempt < max_retries:
                                delay = initial_delay * (2 ** attempt)
                                func_name = getattr(func, "__name__", str(func))
                                logger.warning(
                                    f"[DB_WORKER_RETRY] sqlite3.OperationalError on {func_name} "
                                    f"(attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in {delay:.3f}s..."
                                )
                                self.close_thread_connection()
                                time.sleep(delay)
                                continue
                            else:
                                raise e
                        except Exception as e:
                            raise e

                    if executed_successfully:
                        try:
                            future.set_result(res)
                        except Exception as fe:
                            logger.warning(f"[DB_WORKER] Failed to set future result: {fe}")
                except Exception as e:
                    logger.exception(f"[DB_WORKER_ERROR] Write task failed: {e}")
                    try:
                        future.set_exception(e)
                    except Exception as fe:
                        logger.warning(f"[DB_WORKER] Failed to set future exception: {fe}")
                finally:
                    self.close_thread_connection()
                    self._thread_local.is_worker = True
                    self._write_queue.task_done()
            except Exception as e:
                import traceback
                print(f"[DB_WORKER_ERROR_CRITICAL] {e}\n{traceback.format_exc()}")


    def _get_conn(self):
        if self.filepath == ":memory:":
            if not hasattr(self, "_master_conn") or self._master_conn is None:
                self._master_conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
                self._init_db()
            conn = sqlite3.connect("file::memory:?cache=shared", uri=True, timeout=10.0, isolation_level=None)
        else:
            conn = sqlite3.connect(self.filepath, timeout=10.0, isolation_level=None)
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
        already_in_tx = getattr(conn, "in_transaction", False)
        try:
            if not already_in_tx:
                conn.execute("BEGIN DEFERRED")
            yield conn
            if not already_in_tx:
                conn.execute("COMMIT")
        except Exception:
            if not already_in_tx:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass
                self._thread_local.conn = None
            raise

    @contextmanager
    def write_transaction(self):
        if not hasattr(self._thread_local, "conn") or self._thread_local.conn is None:
            self._thread_local.conn = self._get_conn()
        conn = self._thread_local.conn
        already_in_tx = getattr(conn, "in_transaction", False)
        try:
            if not already_in_tx:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
            if not already_in_tx:
                conn.execute("COMMIT")
                self.write_counter += 1
        except Exception:
            if not already_in_tx:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass
                self._thread_local.conn = None
            raise

    def close_thread_connection(self):
        """Close the thread-local SQLite connection, allowing WAL checkpoint and freeing resources."""
        conn = getattr(self._thread_local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            finally:
                self._thread_local.conn = None

    def close(self):
        if hasattr(self, "columnar_engine") and self.columnar_engine is not None:
            try:
                self.columnar_engine.close()
            except Exception:
                pass

        if hasattr(self, "_write_queue"):
            try:
                self._write_queue.put(None, block=True, timeout=0.5)
                if hasattr(self, "_db_worker_thread") and self._db_worker_thread.is_alive():
                    self._db_worker_thread.join(timeout=2.0)
            except Exception:
                pass
                
        if True:  # self.lock removed for WAL concurrency
            if hasattr(self._thread_local, "conn") and self._thread_local.conn is not None:
                try:
                    self._thread_local.conn.close()
                except Exception:
                    pass
                self._thread_local.conn = None
            if self._master_conn is not None:
                try:
                    self._master_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except Exception:
                    pass
                try:
                    self._master_conn.close()
                except Exception:
                    pass
                self._master_conn = None

    @staticmethod
    def _apply_date_range(query: str, date_column: str, start_date=None, end_date=None):
        """Append date range WHERE/AND clauses and return (query, params)."""
        params = []
        clauses = []
        if start_date:
            clauses.append(f"{date_column} >= ?")
            params.append(start_date)
        if end_date:
            clauses.append(f"{date_column} <= ?")
            params.append(end_date)
        if clauses:
            separator = " WHERE " if " WHERE " not in query.upper() else " AND "
            query += separator + " AND ".join(clauses)
        return query, params

    def flush_queue(self, timeout=5.0):
        """Wait for all pending async write tasks in the write queue to complete."""
        try:
            self.flush_app_usage()
        except Exception:
            pass
        if hasattr(self, "columnar_engine") and self.columnar_engine is not None:
            try:
                self.columnar_engine.flush()
            except Exception:
                pass
        if hasattr(self, "_write_queue") and self._write_queue is not None:
            try:
                self._write_queue.join()
            except Exception:
                pass

    def close_thread_connection(self):
        if True:  # self.lock removed for WAL concurrency
            if hasattr(self._thread_local, "conn") and self._thread_local.conn is not None:
                try:
                    if getattr(self._thread_local.conn, "in_transaction", False):
                        self._thread_local.conn.execute("ROLLBACK")
                except Exception:
                    pass
                try:
                    self._thread_local.conn.close()
                except Exception:
                    pass
                self._thread_local.conn = None


    def _init_db(self):
        with self.write_transaction() as conn:
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
            conn.execute("CREATE INDEX IF NOT EXISTS idx_app_usage_analytics ON app_usage(date, process, duration)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_mode_start ON sessions(mode, start)")
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
            
            # 13 Cognitive Features: New Tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    description TEXT,
                    awarded_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS context_switches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    from_process TEXT,
                    to_process TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_context_switches_ts ON context_switches(timestamp)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT,
                    completed INTEGER DEFAULT 0,
                    created_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS focus_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    duration_minutes INTEGER,
                    task_label TEXT,
                    completed INTEGER,
                    stamina_start REAL,
                    stamina_end REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_focus_sessions_ts ON focus_sessions(timestamp)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gratitude_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE,
                    entry_1 TEXT,
                    entry_2 TEXT,
                    entry_3 TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS calendar_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    start_time TEXT,
                    end_time TEXT
                )
            """)
            
            # Alter sessions table to add flow fields if not present
            info = conn.execute("PRAGMA table_info(sessions)").fetchall()
            cols = [row["name"] for row in info]
            if "is_flow" not in cols:
                conn.execute("ALTER TABLE sessions ADD COLUMN is_flow INTEGER DEFAULT 0")
            if "flow_duration" not in cols:
                conn.execute("ALTER TABLE sessions ADD COLUMN flow_duration REAL DEFAULT 0.0")
            
            cursor = conn.execute("SELECT COUNT(*) FROM settings")
            if cursor.fetchone()[0] == 0:
                for k, v in DEFAULT_SETTINGS.items():
                    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (k, json.dumps(v)))

    def _migrate_legacy_json(self):
        if self.filepath == ":memory:":
            return
        legacy_json_path = self.filepath.replace(".db", ".json")
        if os.path.exists(legacy_json_path) and os.path.isfile(legacy_json_path):
            with self.write_transaction() as conn:
                row = conn.execute("SELECT value FROM metadata WHERE key = 'migrated_from_json'").fetchone()
                if row and row["value"] == "true":
                    return
            print(f"Legacy JSON database found at {legacy_json_path}. Migrating to SQLite...")
            try:
                with open(legacy_json_path, "r", encoding="utf-8") as f:
                    legacy_data = json.load(f)
                if not isinstance(legacy_data, dict):
                    legacy_data = {}
                with self.write_transaction() as conn:
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

    def _merge_legacy_db(self):
        if self.filepath == ":memory:":
            return
        target_app_db = os.path.join(DEFAULT_DATA_DIR, "mind_flow_data.db")
        if os.path.abspath(self.filepath) != os.path.abspath(target_app_db):
            return
        legacy_db_path = r"C:\MIND\mind_flow_data.db"
        if os.path.exists(legacy_db_path) and os.path.abspath(legacy_db_path) != os.path.abspath(self.filepath):
            try:
                with self.write_transaction() as conn:
                    row = conn.execute("SELECT value FROM metadata WHERE key = 'merged_legacy_db'").fetchone()
                    if row and row["value"] == "true":
                        return
                src_conn = sqlite3.connect(legacy_db_path)
                src_cur = src_conn.cursor()
                with self.write_transaction() as conn:
                    # Reflections
                    src_refs = src_cur.execute("SELECT timestamp, energy_level, friction_level, summary, mood, sleep_hours, sleep_quality FROM reflections").fetchall()
                    dst_refs = set(r["timestamp"] for r in conn.execute("SELECT timestamp FROM reflections").fetchall())
                    for r in src_refs:
                        if r[0] not in dst_refs:
                            conn.execute("INSERT INTO reflections (timestamp, energy_level, friction_level, summary, mood, sleep_hours, sleep_quality) VALUES (?, ?, ?, ?, ?, ?, ?)", r)
                            dst_refs.add(r[0])
                    # Sessions
                    src_sess = src_cur.execute("SELECT mode, start, end, duration, brain_dump, bypassed FROM sessions").fetchall()
                    dst_sess = set(s["start"] for s in conn.execute("SELECT start FROM sessions").fetchall())
                    for s in src_sess:
                        if s[1] not in dst_sess:
                            conn.execute("INSERT INTO sessions (mode, start, end, duration, brain_dump, bypassed) VALUES (?, ?, ?, ?, ?, ?)", s)
                            dst_sess.add(s[1])
                    # App Usage
                    src_app = src_cur.execute("SELECT date, process, title, titles, duration FROM app_usage").fetchall()
                    dst_app = set((a["date"], a["process"]) for a in conn.execute("SELECT date, process FROM app_usage").fetchall())
                    for a in src_app:
                        if (a[0], a[1]) not in dst_app:
                            conn.execute("INSERT OR IGNORE INTO app_usage (date, process, title, titles, duration) VALUES (?, ?, ?, ?, ?)", a)
                            dst_app.add((a[0], a[1]))
                    conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('merged_legacy_db', 'true')")
                src_conn.close()
            except Exception as e:
                print(f"[MIND-FLOW] Warning: Legacy SQLite database merge failed: {e}")

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


    @queued_write
    def save(self, sync=False):
        self.flush_app_usage()

    def get_settings(self):
        with MindFlowDB._settings_lock:
            if MindFlowDB._settings_cache is not None:
                res = copy.deepcopy(MindFlowDB._settings_cache)
                if "is_cloud_sync" not in res:
                    try:
                        from backend.workspace_manager import WorkspaceManager
                        res["is_cloud_sync"] = WorkspaceManager(self.filepath if self.filepath != ":memory:" else DEFAULT_DATA_DIR).is_cloud_sync
                    except Exception:
                        res["is_cloud_sync"] = False
                return res
            
            settings = {}
            with self.connection() as conn:
                for row in conn.execute("SELECT key, value FROM settings"):
                    settings[row["key"]] = json.loads(row["value"])
            for k, v in DEFAULT_SETTINGS.items():
                if k not in settings:
                    settings[k] = copy.deepcopy(v)
            MindFlowDB._settings_cache = settings
            res = copy.deepcopy(MindFlowDB._settings_cache)
            if "is_cloud_sync" not in res:
                try:
                    from backend.workspace_manager import WorkspaceManager
                    res["is_cloud_sync"] = WorkspaceManager(self.filepath if self.filepath != ":memory:" else DEFAULT_DATA_DIR).is_cloud_sync
                except Exception:
                    res["is_cloud_sync"] = False
            return res

    def get_current_goal(self):
        if True:  # self.lock removed for WAL concurrency
            with self.connection() as conn:
                row = conn.execute("SELECT value FROM metadata WHERE key = 'current_goal'").fetchone()
                return row["value"] if row else ""

    @queued_write
    def set_current_goal(self, goal):
        if True:  # self.lock removed for WAL concurrency
            with self.write_transaction() as conn:
                conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('current_goal', ?)", (str(goal).strip(),))

    def get_hydration(self):
        if True:  # self.lock removed for WAL concurrency
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

    @queued_write
    def increment_hydration(self, cups=None):
        if True:  # self.lock removed for WAL concurrency
            today_str = datetime.today().date().isoformat()
            settings = self.get_settings()
            with self.write_transaction() as conn:
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
        if True:  # self.lock removed for WAL concurrency
            if not date_str:
                date_str = datetime.today().date().isoformat()
            with self.connection() as conn:
                row = conn.execute("SELECT count FROM steps WHERE date = ?", (date_str,)).fetchone()
                return row["count"] if row else 0

    @queued_write
    def log_steps(self, count, date_str=None):
        if True:  # self.lock removed for WAL concurrency
            if not date_str:
                date_str = datetime.today().date().isoformat()
            try:
                count_val = int(count)
            except (ValueError, TypeError):
                count_val = 0
            with self.write_transaction() as conn:
                conn.execute("INSERT OR REPLACE INTO steps (date, count) VALUES (?, ?)", (date_str, count_val))
            return count_val

    def get_sleep(self, date_str=None):
        if True:  # self.lock removed for WAL concurrency
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

    @queued_write
    def log_sleep(self, hours, quality, date_str=None):
        if True:  # self.lock removed for WAL concurrency
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
            with self.write_transaction() as conn:
                conn.execute("INSERT OR REPLACE INTO sleep (date, hours, quality) VALUES (?, ?, ?)", (date_str, hours_val, quality_val))
            return {"hours": hours_val, "quality": quality_val}

    def get_sleep_list(self, start_date=None, end_date=None):
        if True:  # self.lock removed for WAL concurrency
            sleep = []
            query, params = self._apply_date_range("SELECT date, hours, quality FROM sleep", "date", start_date, end_date)
            query += " ORDER BY date ASC"
            with self.connection() as conn:
                for row in conn.execute(query, params):
                    sleep.append({
                        "date": row["date"],
                        "hours": row["hours"],
                        "quality": row["quality"]
                    })
            return sleep

    def get_steps_list(self, start_date=None, end_date=None):
        if True:  # self.lock removed for WAL concurrency
            steps = []
            query, params = self._apply_date_range("SELECT date, count FROM steps", "date", start_date, end_date)
            query += " ORDER BY date ASC"
            with self.connection() as conn:
                for row in conn.execute(query, params):
                    steps.append({
                        "date": row["date"],
                        "count": row["count"]
                    })
            return steps

    @queued_write
    def update_settings(self, settings_dict):
        with MindFlowDB._settings_lock:
            settings = self.get_settings()
            for k, v in settings_dict.items():
                if k == "enable_eye_care_nudges":
                    k = "enable_eyecare_nudges"
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
                    elif k in ["adaptive_timers_enabled", "eye_care_mode", "circadian_forecast_enabled", "enable_desktop_toasts", "enable_audio_chimes", "enable_distraction_nudges", "enable_thrashing_nudges", "enable_eyecare_nudges", "enable_hydration_nudges"]:
                        if isinstance(v, str):
                            settings[k] = v.lower() in ["true", "1", "yes"]
                        else:
                            settings[k] = bool(v)
                    elif k == "proactivity_level":
                        val = str(v).strip().lower()
                        if val in ["disabled", "gentle", "balanced", "strict"]:
                            settings[k] = val
                    elif k == "circadian_forecast_sensitivity":
                        val = str(v).strip().lower()
                        if val in ["low", "medium", "high"]:
                            settings[k] = val
                    elif k == "zen_level":
                        val = str(v).strip().lower()
                        if val in ["tranquil", "balanced", "sprint", "whisper", "drift", "deep", "void"]:
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
                                pat = str(r["pattern"]).strip()
                                cat = str(r["category"]).strip().lower()
                                if is_safe_regex(pat):
                                    rules.append({
                                        "pattern": pat,
                                        "category": cat
                                    })
                        settings[k] = rules[:50]
                    elif isinstance(v, list):
                        filtered = [str(x).strip().lower() for x in v if x]
                        settings[k] = filtered[:50]
            with self.write_transaction() as conn:
                for k, v in settings.items():
                    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, json.dumps(v)))
            self.clear_analytics_cache()
            MindFlowDB._settings_cache = None
            clear_regex_caches()

    def get_app_rules(self):
        settings = self.get_settings()
        work_kw = settings.get("work_keywords", [])
        recharge_kw = settings.get("recharge_keywords", [])
        neutral_kw = settings.get("neutral_keywords", [])
        rules = []
        seen = set()
        for kw in work_kw:
            if kw and kw not in seen:
                rules.append({"app_name": kw, "category": "work"})
                seen.add(kw)
        for kw in recharge_kw:
            if kw and kw not in seen:
                rules.append({"app_name": kw, "category": "recharge"})
                seen.add(kw)
        for kw in neutral_kw:
            if kw and kw not in seen:
                rules.append({"app_name": kw, "category": "neutral"})
                seen.add(kw)
        return rules

    @queued_write
    def recategorize_app(self, app_name, target_category):
        name = str(app_name).strip().lower()
        cat = str(target_category).strip().lower()
        if not name or cat not in ["work", "recharge", "neutral"]:
            return
        
        base_name = name[:-4] if name.endswith(".exe") else name
        exe_name = f"{base_name}.exe"
        targets_to_remove = {name, base_name, exe_name}

        settings = self.get_settings()
        work_kw = [x for x in settings.get("work_keywords", []) if str(x).strip().lower() not in targets_to_remove]
        recharge_kw = [x for x in settings.get("recharge_keywords", []) if str(x).strip().lower() not in targets_to_remove]
        neutral_kw = [x for x in settings.get("neutral_keywords", []) if str(x).strip().lower() not in targets_to_remove]
        
        # Deduplicate defensively across all lists
        seen_all = set()
        clean_work = []
        for x in work_kw:
            xl = str(x).strip().lower()
            if xl and xl not in seen_all and xl not in targets_to_remove:
                clean_work.append(x)
                seen_all.add(xl)

        clean_recharge = []
        for x in recharge_kw:
            xl = str(x).strip().lower()
            if xl and xl not in seen_all and xl not in targets_to_remove:
                clean_recharge.append(x)
                seen_all.add(xl)

        clean_neutral = []
        for x in neutral_kw:
            xl = str(x).strip().lower()
            if xl and xl not in seen_all and xl not in targets_to_remove:
                clean_neutral.append(x)
                seen_all.add(xl)

        if cat == "work":
            clean_work.append(name)
        elif cat == "recharge":
            clean_recharge.append(name)
        elif cat == "neutral":
            clean_neutral.append(name)
            
        self.update_settings({
            "work_keywords": clean_work,
            "recharge_keywords": clean_recharge,
            "neutral_keywords": clean_neutral
        })
        self.clear_analytics_cache()

    @queued_write
    def delete_app_rule(self, app_name):
        name = str(app_name).strip().lower()
        if not name:
            return
        base_name = name[:-4] if name.endswith(".exe") else name
        exe_name = f"{base_name}.exe"
        targets_to_remove = {name, base_name, exe_name}

        settings = self.get_settings()
        work_kw = [x for x in settings.get("work_keywords", []) if str(x).strip().lower() not in targets_to_remove]
        recharge_kw = [x for x in settings.get("recharge_keywords", []) if str(x).strip().lower() not in targets_to_remove]
        neutral_kw = [x for x in settings.get("neutral_keywords", []) if str(x).strip().lower() not in targets_to_remove]
        self.update_settings({
            "work_keywords": work_kw,
            "recharge_keywords": recharge_kw,
            "neutral_keywords": neutral_kw
        })
        self.clear_analytics_cache()

    def get_recent_apps(self, limit=30):
        with self.connection() as conn:
            rows = conn.execute("""
                SELECT DISTINCT process, title
                FROM app_usage
                WHERE process IS NOT NULL AND process != '' AND process != 'None'
                ORDER BY date DESC
                LIMIT ?
            """, (limit,)).fetchall()
            apps = []
            seen = set()
            for row in rows:
                proc = row["process"]
                proc_lower = proc.lower()
                if proc_lower not in seen:
                    seen.add(proc_lower)
                    disp = proc.replace(".exe", "").replace(".EXE", "")
                    disp = disp.capitalize() if len(disp) > 0 else disp
                    apps.append({
                        "process": proc,
                        "display_name": disp,
                        "last_title": row["title"] or ""
                    })
            return apps

    @queued_write
    def log_session(self, mode, start_time, end_time, brain_dump=None, bypassed=False, is_flow=False, flow_duration=0.0):
        duration = (end_time - start_time).total_seconds()
        if duration < 5:
            return
        if True:  # self.lock removed for WAL concurrency
            with self.write_transaction() as conn:
                conn.execute("""
                    INSERT INTO sessions (mode, start, end, duration, brain_dump, bypassed, is_flow, flow_duration)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (mode, start_time.isoformat(), end_time.isoformat(), duration, brain_dump, 1 if bypassed else 0, 1 if is_flow else 0, flow_duration))

            self.clear_analytics_cache()
    @queued_write
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
        if True:  # self.lock removed for WAL concurrency
            timestamp = datetime.now().isoformat()
            with self.write_transaction() as conn:
                conn.execute("""
                    INSERT INTO reflections (timestamp, energy_level, friction_level, summary, mood, sleep_hours, sleep_quality)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, energy_val, friction_val, str(summary).strip(), str(mood).strip() if mood else None, sleep_hours_val, sleep_quality_val))
            self.clear_analytics_cache()
            return {
                "timestamp": timestamp,
                "energy_level": energy_val,
                "friction_level": friction_val,
                "summary": str(summary).strip(),
                "mood": str(mood).strip() if mood else None,
                "sleep_hours": sleep_hours_val,
                "sleep_quality": sleep_quality_val
            }

    def get_reflections(self, start_date=None, end_date=None):
        if True:  # self.lock removed for WAL concurrency
            reflections = []
            query, params = self._apply_date_range("SELECT timestamp, energy_level, friction_level, summary, mood, sleep_hours, sleep_quality FROM reflections", "date(timestamp)", start_date, end_date)
            query += " ORDER BY id ASC"
            with self.connection() as conn:
                for row in conn.execute(query, params):
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

    def get_sessions(self, start_date=None, end_date=None):
        if True:  # self.lock removed for WAL concurrency
            sessions = []
            query, params = self._apply_date_range("SELECT mode, start, end, duration, brain_dump, bypassed, is_flow, flow_duration FROM sessions", "date(start)", start_date, end_date)
            query += " ORDER BY id ASC"
            with self.connection() as conn:
                for row in conn.execute(query, params):
                    sessions.append({
                        "mode": row["mode"],
                        "start": row["start"],
                        "end": row["end"],
                        "duration": row["duration"],
                        "brain_dump": row["brain_dump"],
                        "bypassed": bool(row["bypassed"]),
                        "is_flow": bool(row["is_flow"]) if row["is_flow"] is not None else False,
                        "flow_duration": row["flow_duration"] if row["flow_duration"] is not None else 0.0
                    })
            return sessions

    @queued_write
    def log_app_usage(self, process, title, duration, category=None):
        if not process or process == "None":
            return
        with self.buffer_lock:
            key = (process, title)
            self.app_usage_buffer[key] = self.app_usage_buffer.get(key, 0) + duration

        if hasattr(self, "columnar_engine") and self.columnar_engine is not None:
            try:
                cat = category or self.categorize_app(process, title)
                self.columnar_engine.append_window_log(time.time(), process, title, cat, duration)
            except Exception:
                pass

    def categorize_app(self, process, title):
        settings = self.get_settings()
        proc_title = f"{process or ''} {title or ''}".strip().lower()

        custom_rules = settings.get("custom_rules", [])
        for rule in custom_rules:
            pat = rule.get("pattern")
            cat = rule.get("category")
            if pat and cat and matches_keyword(pat, proc_title):
                return cat.lower()

        if matches_any_keyword(settings.get("work_keywords", []), proc_title):
            return "work"
        elif matches_any_keyword(settings.get("recharge_keywords", []), proc_title):
            return "recharge"
        elif matches_any_keyword(settings.get("neutral_keywords", []), proc_title):
            return "neutral"
        return "neutral"

    def get_daily_productivity_trends(self, days=7):
        if hasattr(self, "columnar_engine") and self.columnar_engine is not None:
            return self.columnar_engine.get_daily_productivity_trends(days)
        return []

    def get_category_breakdown(self, start_ts=None, end_ts=None):
        if start_ts is None:
            end_ts = time.time()
            start_ts = end_ts - (86400 * 7)
        if hasattr(self, "columnar_engine") and self.columnar_engine is not None:
            return self.columnar_engine.get_category_breakdown(start_ts, end_ts)
        return {"work": 0.0, "rest": 0.0, "recharge": 0.0, "neutral": 0.0}

    def get_fatigue_duration_analytics(self, days=30):
        if hasattr(self, "columnar_engine") and self.columnar_engine is not None:
            return self.columnar_engine.get_fatigue_duration_analytics(days)
        return {
            "total_work_seconds": 0.0,
            "total_rest_seconds": 0.0,
            "avg_daily_work_seconds": 0.0,
            "longest_continuous_work_seconds": 0.0,
            "fatigue_risk_score": 0.0,
            "hourly_distribution": [0.0] * 24,
            "analysis_period_days": days
        }

    @queued_write
    def flush_app_usage(self):
        with self.buffer_lock:
            if not self.app_usage_buffer:
                return
            today_str = datetime.today().date().isoformat()
            if True:  # self.lock removed for WAL concurrency
                with self.write_transaction() as conn:
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
                    # Do not clear the global status/analytics cache on routine 10s app usage ticks
                    # to prevent cache thrashing on 1Hz /api/status polls.
            self.app_usage_buffer.clear()
            try:
                with self.connection() as conn:
                    conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
            except Exception:
                pass


    def get_app_usage(self, start_date=None, end_date=None):
        self.flush_app_usage()
        if True:  # self.lock removed for WAL concurrency
            usage = []
            query, params = self._apply_date_range("SELECT date, process, title, titles, duration FROM app_usage", "date", start_date, end_date)
            query += " ORDER BY date ASC, rowid ASC"
            with self.connection() as conn:
                for row in conn.execute(query, params):
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
            rows = conn.execute("""
                SELECT timestamp, energy_level 
                FROM reflections 
                WHERE timestamp >= ? AND timestamp <= ?
            """, (thirty_days_ago, now.isoformat())).fetchall()
            for r in rows:
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
        settings = self.get_settings()
        now_time = time.time()
        cache = self._adaptive_cache
        write_cnt = self.analytics_write_counter
        if (cache["result"] is not None and
            cache["last_settings"] == settings and
            cache["last_write_counter"] == write_cnt and
            cache["last_checked_date"] == today_date):
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
            cache["last_write_counter"] = write_cnt
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
        cache["last_write_counter"] = write_cnt
        cache["last_checked_date"] = today_date
        cache["last_check_time"] = now_time
        cache["result"] = result
        return result

    def get_cached_status_data(self):
        from datetime import date
        today_date = datetime.today().date()
        today_str = today_date.isoformat()
        now_time = time.time()
        cache = self._status_cache
        write_cnt = self.analytics_write_counter
        if (cache["result"] is not None and
            cache["last_write_counter"] == write_cnt and
            cache["last_checked_date"] == today_date):
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
        cache["last_write_counter"] = write_cnt
        cache["last_checked_date"] = today_date
        cache["last_check_time"] = now_time
        cache["result"] = result
        return result

    def get_battery_state(self) -> dict:
        if True:  # self.lock removed for WAL concurrency
            with self.connection() as conn:
                row = conn.execute(
                    "SELECT current_capacity, consecutive_work_minutes FROM battery_state WHERE id = 1"
                ).fetchone()
                if row:
                    return {"capacity": row[0], "consecutive_work": row[1]}
                else:
                    return {"capacity": 100.0, "consecutive_work": 0.0}

    @queued_write
    def flush_battery_state(self, capacity: float, consecutive_work: float):
        if True:  # self.lock removed for WAL concurrency
            with self.write_transaction() as conn:
                conn.execute("""
                    UPDATE battery_state
                    SET current_capacity = ?, consecutive_work_minutes = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE id = 1
                """, (capacity, consecutive_work))

    # Streaks & Achievements
    def get_streak_info(self):
        import time
        from datetime import datetime, date, timedelta
        today_date = date.today()
        now_time = time.time()
        cache = self._streak_cache
        if (cache["result"] is not None and
            cache["last_write_counter"] == self.analytics_write_counter and
            cache["last_checked_date"] == today_date):
            return cache["result"]
            
        if True:  # self.lock removed for WAL concurrency
            with self.connection() as conn:
                rows = conn.execute("""
                    SELECT DISTINCT SUBSTR(start, 1, 10) as date_str 
                    FROM sessions 
                    WHERE mode = 'work' AND duration > 0
                    ORDER BY date_str ASC
                """).fetchall()
                
                dates = []
                for r in rows:
                    try:
                        dates.append(date.fromisoformat(r["date_str"]))
                    except Exception:
                        pass
                
                if not dates:
                    res = {"current_streak": 0, "longest_streak": 0}
                    cache["result"] = res
                    cache["last_write_counter"] = self.analytics_write_counter
                    cache["last_checked_date"] = today_date
                    cache["last_check_time"] = now_time
                    return res
                
                unique_dates = sorted(list(set(dates)))
                if not unique_dates:
                    res = {"current_streak": 0, "longest_streak": 0}
                    cache["result"] = res
                    cache["last_write_counter"] = self.analytics_write_counter
                    cache["last_checked_date"] = today_date
                    cache["last_check_time"] = now_time
                    return res
                
                longest = 0
                temp_streak = 1
                for i in range(1, len(unique_dates)):
                    if unique_dates[i] - unique_dates[i-1] == timedelta(days=1):
                        temp_streak += 1
                    else:
                        if temp_streak > longest:
                            longest = temp_streak
                        temp_streak = 1
                if temp_streak > longest:
                    longest = temp_streak
                
                today = date.today()
                yesterday = today - timedelta(days=1)
                
                current = 0
                if today in unique_dates or yesterday in unique_dates:
                    idx = len(unique_dates) - 1
                    if unique_dates[idx] == today or unique_dates[idx] == yesterday:
                        current = 1
                        while idx > 0:
                            if unique_dates[idx] - unique_dates[idx-1] == timedelta(days=1):
                                current += 1
                                idx -= 1
                            elif unique_dates[idx] == unique_dates[idx-1]:
                                idx -= 1
                            else:
                                break
                
                res = {"current_streak": current, "longest_streak": max(longest, current)}
                cache["result"] = res
                cache["last_write_counter"] = self.analytics_write_counter
                cache["last_checked_date"] = today_date
                cache["last_check_time"] = now_time
                return res

    def get_focus_streaks(self, days=30):
        from datetime import date, timedelta
        try:
            days = int(days) if days is not None else 30
        except (ValueError, TypeError):
            days = 30
        days = min(max(days, 1), 365)

        streak_info = self.get_streak_info()
        today = date.today()
        start_date = today - timedelta(days=days - 1)

        with self.connection() as conn:
            rows = conn.execute("""
                SELECT SUBSTR(start, 1, 10) as date_str, COUNT(*) as session_count, SUM(duration) as total_duration
                FROM sessions
                WHERE mode = 'work' AND duration > 0 AND SUBSTR(start, 1, 10) >= ?
                GROUP BY date_str
            """, (start_date.isoformat(),)).fetchall()

        history_map = {r["date_str"]: {"sessions": r["session_count"], "duration_minutes": round(r["total_duration"] / 60.0, 1)} for r in rows}

        history = []
        total_focus_days = 0
        for i in range(days):
            cur_date = start_date + timedelta(days=i)
            cur_str = cur_date.isoformat()
            data = history_map.get(cur_str, {"sessions": 0, "duration_minutes": 0.0})
            has_focus = data["sessions"] > 0
            if has_focus:
                total_focus_days += 1
            history.append({
                "date": cur_str,
                "has_focus": has_focus,
                "sessions": data["sessions"],
                "duration_minutes": data["duration_minutes"]
            })

        return {
            "current_streak": streak_info.get("current_streak", 0),
            "longest_streak": streak_info.get("longest_streak", 0),
            "total_focus_days": total_focus_days,
            "history": history
        }

    @queued_write
    def award_achievement(self, name, description):
        from datetime import datetime
        if True:  # self.lock removed for WAL concurrency
            with self.write_transaction() as conn:
                conn.execute("INSERT OR IGNORE INTO achievements (name, description, awarded_at) VALUES (?, ?, ?)",
                             (name, description, datetime.now().isoformat()))
        if hasattr(self, "_achievements_cache") and self._achievements_cache:
            self._achievements_cache["last_write_counter"] = -1
    def get_achievements(self):
        from datetime import date, datetime, timedelta
        now = time.time()
        cache = self._achievements_cache
        write_cnt = self.analytics_write_counter
        if (cache["result"] is not None and 
            cache.get("last_write_counter", -1) == write_cnt ):
            return cache["result"]

        settings = self.get_settings()
        target_cups = settings.get("hydration_target", 8.0)

        # 1. Perform all reads in a single connection block and close it immediately.
        with self.connection() as conn:
            work_row = conn.execute("SELECT COUNT(*) FROM sessions WHERE mode = 'work'").fetchone()
            work_count = work_row[0] if work_row else 0

            hyd_rows = conn.execute("SELECT date, cups FROM hydration WHERE cups >= ? ORDER BY date DESC", (target_cups,)).fetchall()
            hyd_dates_raw = [r["date"] for r in hyd_rows]

            bypass_rows = conn.execute("""
                SELECT date(start) as d, SUM(bypassed) as bcnt 
                FROM sessions 
                GROUP BY d
            """).fetchall()
            bypass_map = {r["d"]: r["bcnt"] for r in bypass_rows}

            sess_dates_rows = conn.execute("SELECT DISTINCT date(start) as d FROM sessions").fetchall()
            sess_dates_raw = [r["d"] for r in sess_dates_rows]

            ref_rows = conn.execute("SELECT timestamp FROM reflections ORDER BY timestamp DESC").fetchall()
            ref_timestamps = [r["timestamp"] for r in ref_rows]

            # Night Owl & Early Bird: check session start times
            time_rows = conn.execute("""
                SELECT SUBSTR(start, 12, 2) as hour_str
                FROM sessions
                WHERE mode = 'work' AND duration > 0
            """).fetchall()

            # Flow Architect: count flow sessions
            flow_row = conn.execute("SELECT COUNT(*) FROM sessions WHERE is_flow = 1").fetchone()
            flow_count = flow_row[0] if flow_row else 0

            # Marathon Runner: check for 2+ hour focus days
            marathon_row = conn.execute("""
                SELECT MAX(daily_total) FROM (
                    SELECT date(start) as d, SUM(duration) as daily_total
                    FROM sessions
                    WHERE mode = 'work'
                    GROUP BY d
                )
            """).fetchone()
            max_daily_focus = marathon_row[0] if marathon_row and marathon_row[0] else 0

        # 2. Run logic and award achievements in memory (asynchronous non-blocking writes)
        streak_info = self.get_streak_info()
        if streak_info["current_streak"] >= 7:
            self.award_achievement("Shield Guardian", "Maintain a 7-day focus tracking streak.", wait=False)

        if work_count >= 1:
            self.award_achievement("First Step", "Log your first deep work focus session.", wait=False)

        if len(hyd_dates_raw) >= 3:
            hyd_dates = []
            for d_str in hyd_dates_raw:
                try:
                    hyd_dates.append(date.fromisoformat(d_str))
                except Exception:
                    pass
            hyd_dates = sorted(list(set(hyd_dates)))
            has_hero = False
            for i in range(2, len(hyd_dates)):
                if (hyd_dates[i] - hyd_dates[i-1] == timedelta(days=1) and 
                    hyd_dates[i-1] - hyd_dates[i-2] == timedelta(days=1)):
                    has_hero = True
                    break
            if has_hero:
                self.award_achievement("Hydration Hero", "Meet your daily hydration target 3 days in a row.", wait=False)

        sess_dates = []
        for d_str in sess_dates_raw:
            try:
                sess_dates.append(date.fromisoformat(d_str))
            except Exception:
                pass
        sess_dates = sorted(list(set(sess_dates)))
        has_perfect_week = False
        temp_consec = 0
        for i in range(len(sess_dates)):
            d_str = sess_dates[i].isoformat()
            if bypass_map.get(d_str, 0) == 0:
                if i > 0 and (sess_dates[i] - sess_dates[i-1] == timedelta(days=1)):
                    temp_consec += 1
                else:
                    temp_consec = 1
            else:
                temp_consec = 0
            if temp_consec >= 7:
                has_perfect_week = True
                break
        if has_perfect_week:
            self.award_achievement("Zero Bypass Week", "Complete a 7-day focus streak without skipping any breaks.", wait=False)

        ref_dates = []
        for ts in ref_timestamps:
            try:
                ref_dates.append(datetime.fromisoformat(ts))
            except Exception:
                pass

        has_mindful = False
        j = 0
        for i in range(len(ref_dates)):
            while j < len(ref_dates) and ref_dates[i] - ref_dates[j] <= timedelta(days=7):
                j += 1
            if (j - i) >= 5:
                has_mindful = True
                break
        if has_mindful:
            self.award_achievement("Mindfulness Master", "Log 5 or more state reflections within a single week.", wait=False)

        # Night Owl: work session after 10 PM
        has_night = False
        for tr in time_rows:
            try:
                h = int(tr["hour_str"])
                if h >= 22:
                    has_night = True
                    break
            except Exception:
                pass
        if has_night:
            self.award_achievement("Night Owl", "Complete a deep focus session after 10 PM.", wait=False)

        # Early Bird: work session before 8 AM
        has_early = False
        for tr in time_rows:
            try:
                h = int(tr["hour_str"])
                if h < 8:
                    has_early = True
                    break
            except Exception:
                pass
        if has_early:
            self.award_achievement("Early Bird", "Complete a deep focus session before 8 AM.", wait=False)

        # Flow Architect: 3+ flow states
        if flow_count >= 3:
            self.award_achievement("Flow Architect", "Enter a flow state 3 separate times.", wait=False)

        # Century Club: 100+ work sessions
        if work_count >= 100:
            self.award_achievement("Century Club", "Log 100 deep work focus sessions.", wait=False)

        # Marathon Runner: 2+ hours focus in one day
        if max_daily_focus >= 7200:
            self.award_achievement("Marathon Runner", "Accumulate 2 or more hours of deep focus in a single day.", wait=False)

        # 3. Fetch final accomplishments list
        with self.connection() as conn:
            cursor = conn.execute("SELECT name, description, awarded_at FROM achievements ORDER BY id ASC")
            res = [dict(row) for row in cursor]

        cache["last_write_counter"] = write_cnt
        cache["last_check_time"] = now
        cache["result"] = res
        return res

    # Daily Focus Score (0 - 100)
    def calculate_focus_score(self, date_str=None):
        from datetime import date
        if date_str is None:
            date_str = date.today().isoformat()
        
        settings = self.get_settings()
        
        if True:  # self.lock removed for WAL concurrency
            with self.connection() as conn:
                ref_rows = conn.execute("""
                    SELECT energy_level, friction_level 
                    FROM reflections 
                    WHERE timestamp LIKE ?
                """, (date_str + "%",)).fetchall()
                
                if ref_rows:
                    avg_energy = sum(r["energy_level"] for r in ref_rows) / len(ref_rows)
                    avg_friction = sum(r["friction_level"] for r in ref_rows) / len(ref_rows)
                else:
                    avg_energy = 3.0
                    avg_friction = 1.0
                
                energy_score = (avg_energy / 5.0) * 40.0
                friction_score = ((5.0 - avg_friction) / 5.0) * 20.0
                
                hyd_row = conn.execute("SELECT cups FROM hydration WHERE date = ?", (date_str,)).fetchone()
                target_cups = settings.get("hydration_target", 8.0)
                current_cups = hyd_row["cups"] if hyd_row else 0.0
                hydration_score = min(1.0, current_cups / max(1.0, target_cups)) * 15.0
                
                sleep_row = conn.execute("SELECT hours, quality FROM sleep WHERE date = ?", (date_str,)).fetchone()
                if sleep_row:
                    sleep_hours = sleep_row["hours"]
                    sleep_quality = sleep_row["quality"]
                else:
                    avg_sleep = conn.execute("SELECT AVG(hours), AVG(quality) FROM sleep").fetchone()
                    sleep_hours = avg_sleep[0] if avg_sleep and avg_sleep[0] else 7.0
                    sleep_quality = avg_sleep[1] if avg_sleep and avg_sleep[1] else 3
                
                sleep_score = ((sleep_quality / 5.0) * 7.5) + (min(8.0, sleep_hours) / 8.0 * 7.5)
                
                bypass_row = conn.execute("""
                    SELECT SUM(bypassed) as bcnt 
                    FROM sessions 
                    WHERE start LIKE ?
                """, (date_str + "%",)).fetchone()
                bypasses = bypass_row["bcnt"] if bypass_row and bypass_row["bcnt"] else 0
                compliance_score = max(0.0, 10.0 - bypasses * 5.0)
                
                total_score = energy_score + friction_score + hydration_score + sleep_score + compliance_score
                return int(round(total_score))

    def get_focus_score_history(self, days=7):
        from datetime import date, timedelta, datetime
        if True:  # self.lock removed for WAL concurrency
            today = date.today()
            start_date = (today - timedelta(days=days - 1))
            start_date_str = start_date.isoformat()
            
            settings = self.get_settings()
            target_cups = settings.get("hydration_target", 8.0)
            
            avg_sleep_hours, avg_sleep_quality = 7.0, 3
            with self.connection() as conn:
                avg_row = conn.execute("SELECT AVG(hours), AVG(quality) FROM sleep").fetchone()
                if avg_row:
                    if avg_row[0] is not None:
                        avg_sleep_hours = avg_row[0]
                    if avg_row[1] is not None:
                        avg_sleep_quality = avg_row[1]
                        
                ref_rows = conn.execute("""
                    SELECT date(timestamp) as d, energy_level, friction_level 
                    FROM reflections 
                    WHERE date(timestamp) >= ?
                """, (start_date_str,)).fetchall()
                
                hyd_rows = conn.execute("""
                    SELECT date, cups 
                    FROM hydration 
                    WHERE date >= ?
                """, (start_date_str,)).fetchall()
                
                sleep_rows = conn.execute("""
                    SELECT date, hours, quality 
                    FROM sleep 
                    WHERE date >= ?
                """, (start_date_str,)).fetchall()
                
                bypass_rows = conn.execute("""
                    SELECT date(start) as d, SUM(bypassed) as bcnt 
                    FROM sessions 
                    WHERE date(start) >= ?
                    GROUP BY d
                """, (start_date_str,)).fetchall()
            
            ref_map = {}
            for r in ref_rows:
                d = r["d"]
                if d not in ref_map:
                    ref_map[d] = {"energy": [], "friction": []}
                ref_map[d]["energy"].append(r["energy_level"])
                ref_map[d]["friction"].append(r["friction_level"])
                
            hyd_map = {r["date"]: r["cups"] for r in hyd_rows}
            sleep_map = {r["date"]: (r["hours"], r["quality"]) for r in sleep_rows}
            bypass_map = {r["d"]: r["bcnt"] for r in bypass_rows}
            
            history = []
            for i in range(days - 1, -1, -1):
                d_str = (today - timedelta(days=i)).isoformat()
                
                if d_str in ref_map:
                    avg_energy = sum(ref_map[d_str]["energy"]) / len(ref_map[d_str]["energy"])
                    avg_friction = sum(ref_map[d_str]["friction"]) / len(ref_map[d_str]["friction"])
                else:
                    avg_energy = 3.0
                    avg_friction = 1.0
                energy_score = (avg_energy / 5.0) * 40.0
                friction_score = ((5.0 - avg_friction) / 5.0) * 20.0
                
                current_cups = hyd_map.get(d_str, 0.0)
                hydration_score = min(1.0, current_cups / max(1.0, target_cups)) * 15.0
                
                if d_str in sleep_map:
                    sh, sq = sleep_map[d_str]
                else:
                    sh, sq = avg_sleep_hours, avg_sleep_quality
                sleep_score = ((sq / 5.0) * 7.5) + (min(8.0, sh) / 8.0 * 7.5)
                
                bypasses = bypass_map.get(d_str, 0)
                compliance_score = max(0.0, 10.0 - bypasses * 5.0)
                
                total_score = int(round(energy_score + friction_score + hydration_score + sleep_score + compliance_score))
                history.append({
                    "date": d_str,
                    "score": total_score
                })
            return history

    # Context Switch Tracker
    @queued_write
    def log_context_switch(self, from_process, to_process):
        from datetime import datetime
        if not from_process or from_process == "None": from_process = "Idle"
        if not to_process or to_process == "None": to_process = "Idle"
        if from_process == to_process:
            return
        if True:  # self.lock removed for WAL concurrency
            with self.write_transaction() as conn:
                conn.execute("""
                    INSERT INTO context_switches (timestamp, from_process, to_process)
                    VALUES (?, ?, ?)
                """, (datetime.now().isoformat(), from_process, to_process))
            self.clear_analytics_cache()

    def get_context_switches(self, date_str=None, limit=200):
        from datetime import date
        if date_str is None:
            date_str = date.today().isoformat()
        if True:  # self.lock removed for WAL concurrency
            with self.connection() as conn:
                query = "SELECT id, timestamp, from_process, to_process FROM context_switches WHERE timestamp LIKE ?"
                params = [date_str + "%"]
                if limit:
                    query += " ORDER BY id ASC LIMIT ?"
                    params.append(limit)
                else:
                    query += " ORDER BY id ASC"
                rows = conn.execute(query, params).fetchall()
                return [dict(r) for r in rows]

    def get_context_switches_hourly(self, date_str=None):
        from datetime import datetime, date
        if date_str is None:
            date_str = date.today().isoformat()
        switches = self.get_context_switches(date_str)
        hourly = [0] * 24
        for sw in switches:
            try:
                dt = datetime.fromisoformat(sw["timestamp"])
                hourly[dt.hour] += 1
            except Exception:
                pass
        return hourly

    # Tasks (Micro-Planner)
    def get_tasks(self):
        if True:  # self.lock removed for WAL concurrency
            with self.connection() as conn:
                rows = conn.execute("SELECT id, text, completed, created_at FROM tasks ORDER BY id ASC").fetchall()
                return [dict(r) for r in rows]

    @queued_write
    def add_task(self, text):
        from datetime import datetime
        if True:  # self.lock removed for WAL concurrency
            with self.write_transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO tasks (text, completed, created_at)
                    VALUES (?, 0, ?)
                """, (text, datetime.now().isoformat()))
                new_id = cursor.lastrowid
            return {"id": new_id, "text": text, "completed": 0}

    @queued_write
    def update_task(self, task_id, completed):
        if True:  # self.lock removed for WAL concurrency
            with self.write_transaction() as conn:
                conn.execute("UPDATE tasks SET completed = ? WHERE id = ?", (completed, task_id))
                return True

    @queued_write
    def delete_task(self, task_id):
        if True:  # self.lock removed for WAL concurrency
            with self.write_transaction() as conn:
                conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                return True

    # Gratitude Journal
    def get_gratitude(self, date_str=None):
        from datetime import date
        if date_str is None:
            date_str = date.today().isoformat()
        if True:  # self.lock removed for WAL concurrency
            with self.connection() as conn:
                row = conn.execute("""
                    SELECT date, entry_1, entry_2, entry_3 
                    FROM gratitude_journal 
                    WHERE date = ?
                """, (date_str,)).fetchone()
                return dict(row) if row else None

    @queued_write
    def add_gratitude(self, date_str, entry_1, entry_2, entry_3):
        if True:  # self.lock removed for WAL concurrency
            with self.write_transaction() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO gratitude_journal (date, entry_1, entry_2, entry_3)
                    VALUES (?, ?, ?, ?)
                """, (date_str, entry_1, entry_2, entry_3))
                return True

    # Recovery Score (Morning Readiness)
    def get_recovery_score(self):
        import time
        from datetime import date, timedelta
        today_date = date.today()
        now_time = time.time()
        cache = self._recovery_cache
        if (cache["result"] is not None and
            cache["last_write_counter"] == self.analytics_write_counter and
            cache["last_checked_date"] == today_date):
            return cache["result"]
            
        today_str = today_date.isoformat()
        yesterday_str = (today_date - timedelta(days=1)).isoformat()
        
        if True:  # self.lock removed for WAL concurrency
            with self.connection() as conn:
                sleep_row = conn.execute("SELECT hours, quality FROM sleep WHERE date = ?", (today_str,)).fetchone()
                if sleep_row:
                    hours = sleep_row["hours"]
                    quality = sleep_row["quality"]
                    sleep_pct = ((hours / 8.0) * 25.0) + ((quality / 5.0) * 25.0)
                    sleep_pct = min(50.0, sleep_pct)
                    has_sleep = True
                else:
                    sleep_pct = 35.0
                    has_sleep = False
                
                yesterday_sess = conn.execute("""
                    SELECT SUM(duration) as work_dur, SUM(bypassed) as bcnt 
                    FROM sessions 
                    WHERE mode = 'work' AND start LIKE ?
                """, (yesterday_str + "%",)).fetchone()
                
                y_work_hours = (yesterday_sess["work_dur"] or 0) / 3600.0
                y_bypasses = yesterday_sess["bcnt"] or 0
                
                fatigue_penalty = (y_work_hours * 4.0) + (y_bypasses * 12.0)
                load_pct = max(0.0, 50.0 - fatigue_penalty)
                
                total_recovery = sleep_pct + load_pct
                total_recovery = max(10, min(100, int(round(total_recovery))))
                
                if total_recovery >= 85:
                    suggested_work = 45
                elif total_recovery >= 70:
                    suggested_work = 30
                elif total_recovery >= 50:
                    suggested_work = 25
                elif total_recovery >= 35:
                    suggested_work = 20
                else:
                    suggested_work = 15
                
                res = {
                    "recovery_score": total_recovery,
                    "suggested_work_minutes": suggested_work,
                    "has_sleep_logged": has_sleep
                }
                cache["result"] = res
                cache["last_write_counter"] = self.analytics_write_counter
                cache["last_checked_date"] = today_date
                cache["last_check_time"] = now_time
                return res

    @queued_write
    def save_calendar_events(self, events):
        """Atomically update calendar_events via queue worker."""
        with self.write_transaction() as conn:
            conn.execute("DELETE FROM calendar_events")
            for ev in events:
                conn.execute("""
                    INSERT INTO calendar_events (title, start_time, end_time)
                    VALUES (?, ?, ?)
                """, (ev.get("title", ""), ev.get("start_time", ""), ev.get("end_time", "")))

    @queued_write
    def log_focus_session(self, duration_minutes, task_label="", completed=1, stamina_start=100.0, stamina_end=100.0):
        """Log a focus session to SQLite via queue worker."""
        timestamp = datetime.now().isoformat()
        with self.write_transaction() as conn:
            conn.execute(
                """
                INSERT INTO focus_sessions (timestamp, duration_minutes, task_label, completed, stamina_start, stamina_end)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (timestamp, int(duration_minutes), str(task_label or ""), int(completed), float(stamina_start), float(stamina_end))
            )
        self.clear_analytics_cache()
        return True

    def get_focus_session_stats(self, days=7):
        """Retrieve aggregated focus session statistics for the last N days."""
        with self.connection() as conn:
            cur = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_sessions,
                    COALESCE(SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END), 0) as completed_sessions,
                    COALESCE(SUM(CASE WHEN completed = 1 THEN duration_minutes ELSE 0 END), 0) as total_focus_minutes,
                    COALESCE(AVG(CASE WHEN completed = 1 THEN duration_minutes ELSE NULL END), 0) as avg_duration
                FROM focus_sessions
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
                """,
                (int(days),)
            )
            row = cur.fetchone()
            if not row:
                return {"total_sessions": 0, "completed_sessions": 0, "total_focus_minutes": 0, "avg_duration": 0.0}
            return {
                "total_sessions": row["total_sessions"],
                "completed_sessions": row["completed_sessions"],
                "total_focus_minutes": row["total_focus_minutes"],
                "avg_duration": round(row["avg_duration"], 1)
            }

Database = MindFlowDB
db = MindFlowDB()




