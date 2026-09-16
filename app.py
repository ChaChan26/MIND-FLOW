"""
MIND-FLOW Desktop Core Application and State Machine orchestrating active window tracking,
heuristic stamina battery modeling, and background server execution.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import io
import subprocess
import json

# Prevent Edge WebView2 from placing renderer/utility sub-processes into Efficiency Mode / EcoQoS (which forces CPU downclocking)
os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--disable-features=UseEcoQoSForBackgroundProcess --disable-background-timer-throttling"



import shutil

class Unbuffered:
    def __init__(self, stream):
        self.stream = stream
    def write(self, data):
        self.stream.write(data)
        self.stream.flush()
    def writelines(self, datas):
        self.stream.writelines(datas)
        self.stream.flush()
    def __getattr__(self, attr):
        return getattr(self.stream, attr)

# Import get_default_data_dir from database to avoid duplicates
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from backend.database import get_default_data_dir

# Redirect standard logs for PyInstaller executable runs
_stdout_file = None
_stderr_file = None

if getattr(sys, 'frozen', False):
    is_gui = "--gui" in sys.argv
    log_suffix = "_gui" if is_gui else ""
    try:
        data_dir = get_default_data_dir()
        os.makedirs(data_dir, exist_ok=True)
        _stdout_file = open(os.path.join(data_dir, f"app{log_suffix}_stdout.log"), "w", encoding="utf-8")
        _stderr_file = open(os.path.join(data_dir, f"app{log_suffix}_stderr.log"), "w", encoding="utf-8")
        sys.stdout = Unbuffered(_stdout_file)
        sys.stderr = Unbuffered(_stderr_file)
    except Exception:
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

import atexit
def close_log_handles():
    global _stdout_file, _stderr_file
    try:
        if _stdout_file:
            _stdout_file.close()
        if _stderr_file:
            _stderr_file.close()
    except Exception:
        pass
atexit.register(close_log_handles)

import time
import random
import math
import ctypes
import socket

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]
import threading
if sys.platform == "win32":
    import winsound
from datetime import datetime, date

PHYSICAL_STRETCHES = [
    "Roll your shoulders backward in a slow circle 5 times.",
    "Gently tilt your head left for 5 seconds, then right for 5 seconds.",
    "Clasp your hands behind your back and push chest forward to stretch shoulders.",
    "Extend your arms forward, link fingers, and stretch your upper back.",
    "Close your eyes, cup your hands over them, and take 3 slow breaths in darkness.",
    "Rotate your wrists in slow circles outward, then inward 5 times."
]

EYE_EXERCISES = [
    "Look at the moving balloon and track it slowly with your eyes only, keeping your head still.",
    "Look at an object at least 20 feet away for 20 seconds, then focus on your finger nearby.",
    "Blink rapidly 10 times to naturally re-moisturize your eyes.",
    "Slowly roll your eyes in a circle clockwise, then counter-clockwise.",
    "Focus on a distant wall, and draw a giant figure-eight with your eyes.",
    "Rub your hands together to warm them, cup them over closed eyes, and rest for 10 seconds."
]

from backend.database import matches_keyword, matches_any_keyword, is_browser_process
from backend.task_classifier import TaskClassifier

from backend.tracker import (
    get_active_window_details, get_active_window_title, get_active_process_name,
    is_passive_viewing_active, get_idle_seconds, is_dashboard_window,
    disable_ecoqos_for_process_tree, assign_self_to_job
)

# Lockout overlay removed

from backend.server import shared_state, db, run_server, SHARED_API_TOKEN
import collections

from backend.nudge_engine import (
    send_system_notification,
    evaluate_proactive_nudges,
    CognitiveNudgeEngine,
)

class CognitiveBattery:
    def __init__(self, capacity: float = 100.0, consecutive_work: float = 0.0):
        try:
            self.capacity = min(max(float(capacity), 0.0), 100.0)
        except (TypeError, ValueError):
            self.capacity = 100.0
        try:
            self.consecutive_work_minutes = float(consecutive_work)
        except (TypeError, ValueError):
            self.consecutive_work_minutes = 0.0
        
        # Tuning parameters
        self.base_drain_per_minute = 0.5    
        self.fatigue_multiplier = 0.035     
        self.rest_recovery_per_minute = 2.5 

    def process_tick(self, is_working: bool, elapsed_minutes: float, mode: str = None, context_switches_per_min: float = 0.0) -> tuple:
        if mode is None:
            mode = "work" if is_working else "rest"
            
        if mode == "work":
            self.consecutive_work_minutes += elapsed_minutes
            penalty = 1.0 + (self.consecutive_work_minutes * self.fatigue_multiplier)
            switch_penalty = 1.0 + (0.15 * max(0.0, context_switches_per_min))
            drain = self.base_drain_per_minute * penalty * switch_penalty * elapsed_minutes
            self.capacity = max(0.0, self.capacity - drain)
        elif mode == "neutral":
            # Neutral mode: preserve capacity and consecutive work minutes
            pass
        else: # recharge or rest
            decay_rate = 3.0
            self.consecutive_work_minutes = max(0.0, self.consecutive_work_minutes - elapsed_minutes * decay_rate)
            recovery = self.rest_recovery_per_minute * elapsed_minutes
            self.capacity = min(100.0, self.capacity + recovery)
            
        return self.capacity, self.consecutive_work_minutes

_REGEX_CACHE_MAX_SIZE = 250
_safe_regex_cache = {}
_regex_cache_lock = threading.Lock()

def clear_app_regex_cache():
    """Clear the in-memory safe regex pattern cache."""
    with _regex_cache_lock:
        _safe_regex_cache.clear()

try:
    from backend.database import register_cache_invalidation_listener
    register_cache_invalidation_listener(clear_app_regex_cache)
except Exception:
    pass

def safe_regex_search(pattern, text, timeout=None, **kwargs):
    """Match a user-provided regex pattern against text using in-process cached compilation.
    
    Patterns are validated with is_safe_regex() to prevent catastrophic backtracking,
    compiled once, and cached in-memory for fast subsequent lookups (<0.01ms per match).
    """
    if not pattern:
        return None
        
    # Fast-path: simple substring check if no regex metacharacters are present
    metacharacters = "*+?{}[]()|^$\\."
    if not any(c in pattern for c in metacharacters):
        return pattern.lower() in text.lower()

    with _regex_cache_lock:
        if pattern in _safe_regex_cache:
            cached = _safe_regex_cache[pattern]
            if cached is None:
                # Previously rejected as unsafe
                return None
            return True if cached.search(text.lower()) else None

        if len(_safe_regex_cache) >= _REGEX_CACHE_MAX_SIZE:
            _safe_regex_cache.clear()

        # Validate and compile new patterns
        from backend.database import is_safe_regex
        if not is_safe_regex(pattern):
            _safe_regex_cache[pattern] = None
            print(f"[Warning] Custom regex pattern '{pattern}' rejected by safety check (possible ReDoS) and has been blacklisted.")
            return None

        import re
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            _safe_regex_cache[pattern] = None
            return None
        
        _safe_regex_cache[pattern] = compiled
        
        return True if compiled.search(text.lower()) else None

# Module-level URL classification keyword constants
DEFAULT_WORK_CONTEXT_WORDS = [
    "tutorial", "course", "learn", "how to", "documentation", "reference", 
    "coding", "programming", "developer", "lecture", "class", "webinar",
    "study", "education", "research", "arxiv", "sciencedirect", "stack overflow", 
    "github", "docs", "wiki", "wikipedia"
]

DEFAULT_NEUTRAL_WORK_SITES = [
    "wikipedia.org", "wikipedia", "stackoverflow", "stack overflow", 
    "github", "gitlab", "bitbucket", "docs.python", "docs.microsoft", 
    "w3schools", "geeksforgeeks", "medium.com", "dev.to", "arxiv.org",
    "sciencedirect.com", "google scholar", "chatgpt", "claude.ai"
]

DEFAULT_ENTERTAINMENT_SITES = [
    "youtube.com", "youtube", "netflix", "crunchyroll", "bilibili", 
    "soundcloud", "spotify", "twitch.tv", "twitch", "anime", "manga", 
    "tập", "episode", "season", "kaguya", "webtoon", "fmoviesto"
]

def classify_activity_mode(active_process, active_title, work_keywords, recharge_keywords, custom_rules=None, neutral_keywords=None):
    """Determine the classification (work, recharge, neutral) based on user rules, 3-Tier TaskClassifier and heuristics."""
    if custom_rules is None:
        try:
            custom_rules = db.get_settings().get("custom_rules", [])
        except Exception:
            custom_rules = []
    if neutral_keywords is None:
        try:
            neutral_keywords = db.get_settings().get("neutral_keywords", [])
        except Exception:
            neutral_keywords = []
            
    if not active_process or not active_title:
        return "neutral"
        
    proc_lower = active_process.lower()
    title_lower = active_title.lower()
    
    # 1. Custom User Regex Mappings
    for rule in custom_rules:
        pattern = rule.get("pattern")
        category = rule.get("category")
        if pattern and category:
            try:
                if safe_regex_search(pattern, title_lower) or safe_regex_search(pattern, proc_lower):
                    return category
            except Exception:
                pass

    # 2. Process-level keyword match (for non-browser applications)
    if not is_browser_process(active_process):
        proc_clean = proc_lower.replace(".exe", "")
        if matches_any_keyword(work_keywords, proc_clean) or matches_any_keyword(work_keywords, proc_lower):
            return "work"
        if matches_any_keyword(recharge_keywords, proc_clean) or matches_any_keyword(recharge_keywords, proc_lower):
            return "recharge"
        if matches_any_keyword(neutral_keywords, proc_clean) or matches_any_keyword(neutral_keywords, proc_lower):
            return "neutral"

    # 3. Browser heuristics & keyword match
    if is_browser_process(active_process):
        is_work = matches_any_keyword(work_keywords, active_title)
        is_recharge = matches_any_keyword(recharge_keywords, active_title)
        is_neutral = matches_any_keyword(neutral_keywords, active_title)
        
        if is_neutral:
            return "neutral"
        
        has_work_context = any(word in title_lower for word in DEFAULT_WORK_CONTEXT_WORDS)
        
        if is_recharge and ("youtube" in title_lower or "youtube" in proc_lower) and has_work_context:
            return "work"
            
        if not is_work and not is_recharge:
            if any(site in title_lower for site in DEFAULT_NEUTRAL_WORK_SITES):
                return "work"

            if any(site in title_lower for site in DEFAULT_ENTERTAINMENT_SITES) and not has_work_context:
                return "recharge"
                
        if is_work:
            return "work"
        elif is_recharge:
            return "recharge"

    # 4. 3-Tier TaskClassifier Evaluation Engine
    cat = TaskClassifier.classify(active_process, active_title)
    if cat == "rest":
        return "recharge"
    return cat

def _execute_mode_transition(
    prev_mode, new_mode, state_start_time, is_flow_session, flow_start_time,
    idle_limit, is_idle_transition, db, shared_state, nudge_state,
    workspace_mgr, battery
):
    """Execute a mode transition: log the ending session, reset timers, swap workspace files.

    Called from two places in the state machine:
      1. External sync (user clicked a mode button in the UI)
      2. Automatic classifier-driven transition (activity changed)

    Returns:
        tuple: (new_current_mode, new_state_start_time, is_flow_session, flow_start_time, work_consecutive_seconds)
    """
    now = datetime.now()

    # Calculate flow state for ending work session
    is_flow = False
    flow_dur = 0.0
    if prev_mode == "work" and is_flow_session:
        is_flow = True
        work_end = now
        if is_idle_transition and flow_start_time:
            from datetime import timedelta
            work_end = max(state_start_time, now - timedelta(seconds=idle_limit))
        if flow_start_time:
            flow_dur = max(0.0, (work_end - flow_start_time).total_seconds())

    # Log the ending session (backdate if idle-triggered rest)
    if is_idle_transition and prev_mode in ["work", "recharge", "neutral"]:
        from datetime import timedelta
        transition_time = max(state_start_time, now - timedelta(seconds=idle_limit))
        db.log_session(prev_mode, state_start_time, transition_time, is_flow=is_flow, flow_duration=flow_dur, wait=False)
        state_start_time = transition_time
    else:
        db.log_session(prev_mode, state_start_time, now, is_flow=is_flow, flow_duration=flow_dur, wait=False)
        state_start_time = now

    # Update shared state
    shared_state["mode_start_time"] = state_start_time
    shared_state["session_extension_seconds"] = 0
    shared_state["current_mode"] = new_mode
    shared_state["elapsed_seconds"] = 0

    # Reset accumulators when leaving work
    if new_mode in ["rest", "recharge"]:
        nudge_state["active_work_seconds"] = 0

    nudge_state["distraction_dwell_start"] = None

    # Swap workspace files asynchronously and serially
    if workspace_mgr:
        try:
            from backend.thread_pools import workspace_executor
            workspace_executor.submit(workspace_mgr.transition_workspace, prev_mode, new_mode)
        except Exception as e:
            print(f"Error transitioning workspace: {e}")

    return new_mode, state_start_time, False, None, 0

def main_state_machine(gui_process=None):
    """Background thread checking active windows and tracking idle state."""
    print("MIND-FLOW Core State Machine started.")
    if sys.platform == "win32":
        try:
            import ctypes
            # COINIT_MULTITHREADED = 0x2, matching IMMDevice/IMMDeviceEnumerator multi-threaded apartment model
            ctypes.windll.ole32.CoInitializeEx(None, 2)
        except Exception as e:
            print(f"Error initializing COM in state machine: {e}")

    # Initialize workspace manager and clean up leftovers
    try:
        from backend.workspace_manager import WorkspaceManager
        workspace_mgr = WorkspaceManager(get_default_data_dir())
        workspace_mgr.sweep_back_all_async(timeout=5.0)
    except Exception as e:
        print(f"Error initializing WorkspaceManager: {e}")
        workspace_mgr = None

    # Seed initial daily reflection if none exist for today (optimized with reverse search)
    try:
        from datetime import date
        today_str = date.today().isoformat()
        reflections = db.get_reflections()
        has_today_refl = False
        for r in reversed(reflections):
            if r["timestamp"].startswith(today_str):
                has_today_refl = True
                break
            try:
                if datetime.fromisoformat(r["timestamp"]).date() < date.today():
                    break
            except Exception:
                pass
        if not has_today_refl:
            db.add_reflection(5, 1, "[Autopilot] Cognitive Companion active for the day")
            print("Autopilot: Seeded initial daily reflection (Energy: 5, Friction: 1)")
    except Exception as e:
        print(f"Error seeding initial reflection: {e}")

    # App variables
    current_mode = "neutral"
    shared_state["current_mode"] = current_mode
    state_start_time = datetime.now()
    shared_state["mode_start_time"] = state_start_time
    
    # Flow state tracking
    is_flow_session = False
    flow_start_time = None
    work_consecutive_seconds = 0
    
    # Initialize shared app tracking variables
    shared_state["last_app_process"] = None
    shared_state["last_app_title"] = None
    shared_state["app_accumulated_seconds"] = 0
    shared_state["last_hwnd"] = None

    # Run initial EcoQoS disabling
    disable_ecoqos_for_process_tree()

    # Initialize Cognitive Battery from database
    try:
        initial_battery = db.get_battery_state()
        battery = CognitiveBattery(
            capacity=initial_battery.get('capacity', 100.0),
            consecutive_work=initial_battery.get('consecutive_work', 0.0)
        )
    except Exception as e:
        print(f"Error loading initial battery state: {e}")
        battery = CognitiveBattery(capacity=100.0, consecutive_work=0.0)

    # Share initial state immediately
    shared_state['battery_capacity'] = battery.capacity
    shared_state['battery_consecutive_work'] = battery.consecutive_work_minutes

    ticks_since_flush = 0
    tick_duration_seconds = 1.0
    tick_duration_minutes = tick_duration_seconds / 60.0

    # Register exit handler to flush battery state to DB
    import atexit
    @atexit.register
    def exit_flush():
        try:
            db.flush_battery_state(battery.capacity, battery.consecutive_work_minutes)
            print("Autopilot: Flushed final battery state to database via atexit.")
        except Exception as e:
            print(f"Error flushing battery state on exit: {e}")
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.ole32.CoUninitialize()
            except Exception:
                pass

    last_tick_monotonic = time.monotonic()
    last_classified_process = None
    last_classified_title = None
    last_classified_mode = "neutral"
    last_settings = None
    last_recovery_fetch_time = 0
    cached_recovery_data = None
    context_switch_deque = collections.deque(maxlen=30)
    nudge_state = {
        "last_nudges": {},
        "distraction_dwell_start": None,
        "active_work_seconds": 0,
        "active_hydration_seconds": 0,
        "manual_override_until": 0.0
    }

    try:
        from backend import tracker
        if tracker.start_event_listener():
            print("[Tracker] Event-driven OS window listener active.")
            import atexit
    except Exception as e:
        print(f"[Tracker] Warning: failed to start event listener: {e}")

    main_state_machine._start_loop_time = time.time()
    while True:
        time.sleep(1.0)
        
        if shared_state.get("lockout_end_time"):
            state_start_time = shared_state.pop("lockout_end_time")
            shared_state["mode_start_time"] = state_start_time
            shared_state["elapsed_seconds"] = 0
            last_tick_monotonic = time.monotonic()
            
        now_monotonic = time.monotonic()
        elapsed_tick = now_monotonic - last_tick_monotonic
        last_tick_monotonic = now_monotonic
        
        if elapsed_tick > 10.0:
            suspended_sec = elapsed_tick - 1.0
            print(f"[System Resume] Detected suspension of {suspended_sec:.1f}s. Resetting state timers and recovering battery.")
            
            # Log current session up to transition point
            if current_mode not in ["neutral", "rest"]:
                from datetime import timedelta
                transition_time = datetime.now() - timedelta(seconds=suspended_sec)
                is_flow = False
                flow_dur = 0.0
                if current_mode == "work" and is_flow_session:
                    is_flow = True
                    if flow_start_time:
                        flow_dur = max(0.0, (transition_time - flow_start_time).total_seconds())
                try:
                    db.log_session(current_mode, state_start_time, transition_time, is_flow=is_flow, flow_duration=flow_dur, wait=False)
                except Exception as e:
                    print(f"Error logging session on resume: {e}")
            
            # Recover battery capacity & decay work streak
            try:
                battery.process_tick(is_working=False, elapsed_minutes=suspended_sec / 60.0, mode="rest")
                shared_state['battery_capacity'] = battery.capacity
                shared_state['battery_consecutive_work'] = battery.consecutive_work_minutes
                db.flush_battery_state(battery.capacity, battery.consecutive_work_minutes, wait=False)
                db.save(wait=False)
            except Exception as e:
                print(f"Error updating battery on resume: {e}")
                
            # Transition to rest / reset start time
            current_mode = "rest"
            shared_state["current_mode"] = current_mode
            state_start_time = datetime.now()
            shared_state["mode_start_time"] = state_start_time
            shared_state["elapsed_seconds"] = 0
            is_flow_session = False
            flow_start_time = None
            work_consecutive_seconds = 0
            
            # Invalidate classification cache on resume
            last_classified_process = None
            last_classified_title = None
            
            try:
                db.close_thread_connection()
            except Exception:
                pass
            continue
        
        # Check if standalone GUI process exited
        if gui_process and hasattr(gui_process, 'poll') and gui_process.poll() is not None:
            start_loop_time = getattr(main_state_machine, "_start_loop_time", None)
            if start_loop_time and (time.time() - start_loop_time < 5.0) and not getattr(main_state_machine, "_fallback_opened", False):
                main_state_machine._fallback_opened = True
                print("[MIND-FLOW] Standalone window exited prematurely. Launching in default web browser...")
                import webbrowser
                from backend.server import SHARED_API_TOKEN
                port_num = shared_state.get("server_port", 5000)
                webbrowser.open(f"http://127.0.0.1:{port_num}/?token={SHARED_API_TOKEN}")
                gui_process = None
            else:
                print("MIND-FLOW dashboard window closed.")
                
                # Flush app tracking
                last_proc = shared_state.get("last_app_process")
                last_title = shared_state.get("last_app_title")
                accum_sec = shared_state.get("app_accumulated_seconds", 0)
                if last_proc and accum_sec > 0:
                    try:
                        db.log_app_usage(last_proc, last_title, accum_sec, wait=False)
                    except Exception as e:
                        print(f"Error logging app usage on GUI close: {e}")
                
                if workspace_mgr:
                    try:
                        workspace_mgr.sweep_back_all_async(timeout=5.0)
                    except Exception as e:
                        print(f"Error sweeping workspace on GUI exit: {e}")
                db.log_session(current_mode, state_start_time, datetime.now(), wait=False)
                db.save()
                try:
                    db.flush_queue()
                except Exception:
                    pass
                try:
                    db.close()
                except Exception:
                    pass
                try:
                    from backend.thread_pools import shutdown_all
                    shutdown_all(wait=True)
                except Exception:
                    pass
                try:
                    from backend import tracker
                    tracker.stop_event_listener()
                except Exception:
                    pass
                sys.exit(0)
        
        # If user deactivated companion tracking, bypass state machine checks and sweep back workspace
        if not shared_state["tracking_active"]:
            # Flush app tracking
            last_proc = shared_state.get("last_app_process")
            last_title = shared_state.get("last_app_title")
            accum_sec = shared_state.get("app_accumulated_seconds", 0)
            if last_proc and accum_sec > 0:
                try:
                    db.log_app_usage(last_proc, last_title, accum_sec, wait=False)
                except Exception as e:
                    print(f"Error logging app usage on pause: {e}")
                shared_state["last_app_process"] = None
                shared_state["last_app_title"] = None
                shared_state["app_accumulated_seconds"] = 0
            
            if current_mode != "neutral":
                print(f"Companion disabled: transitioning {current_mode} -> neutral")
                db.log_session(current_mode, state_start_time, datetime.now(), wait=False)
                current_mode = "neutral"
                state_start_time = datetime.now()
                shared_state["mode_start_time"] = state_start_time
                if workspace_mgr:
                    try:
                        workspace_mgr.sweep_back_all_async(timeout=5.0)
                    except Exception as e:
                        print(f"Error sweeping workspace on tracking disable: {e}")
            
            shared_state["active_window_title"] = "Companion Paused"
            shared_state["active_process_name"] = "Paused"
            shared_state["current_mode"] = "neutral"
            shared_state["elapsed_seconds"] = 0
            shared_state["idle_seconds"] = 0
            try:
                db.close_thread_connection()
            except Exception:
                pass
            continue

        # Get inputs
        idle_sec = get_idle_seconds()
        try:
            idle_sec_val = float(idle_sec)
        except (TypeError, ValueError):
            idle_sec_val = 0.0

        # Passive viewing check: override idle state if audio is playing in a video/meeting app
        if idle_sec_val >= 5:
            prev_title = shared_state.get("active_window_title")
            prev_proc = shared_state.get("active_process_name")
            if prev_title and prev_proc and is_passive_viewing_active(prev_proc, prev_title):
                idle_sec_val = 0.0

        shared_state["idle_seconds"] = int(idle_sec_val)

        # Optimize polling overhead: reuse previous details when idle
        if idle_sec_val > 5 and shared_state.get("active_window_title") not in [None, "None", "Detecting...", "Paused"]:
            active_title = shared_state.get("active_window_title", "None")
            active_process = shared_state.get("active_process_name", "None")
        else:
            if sys.platform == "win32":
                active_title, active_process = get_active_window_details()
            else:
                # macOS/Linux fallback throttling: poll at most once every 2 seconds
                current_time = time.time()
                if not hasattr(main_state_machine, "_last_unix_poll"):
                    main_state_machine._last_unix_poll = 0.0
                
                if current_time - main_state_machine._last_unix_poll >= 2.0:
                    active_title, active_process = get_active_window_details()
                    main_state_machine._last_unix_poll = current_time
                else:
                    active_title = shared_state.get("active_window_title", "None")
                    active_process = shared_state.get("active_process_name", "None")

        shared_state["active_window_title"] = active_title
        shared_state["active_process_name"] = active_process
        
        # Track last active external window and process (ignoring dashboard focus shifts)
        is_dashboard = is_dashboard_window(active_process, active_title)
        is_invalid = active_title in ["None", "None Detected", "Companion Paused", "Offline", "Detecting..."]
        
        if not is_dashboard and not is_invalid:
            shared_state["last_external_window"] = active_title
            shared_state["last_external_process"] = active_process

        # App tracking logic
        # We only track if user is active (idle_sec_val < 5) and the app is not Paused/None/Dashboard
        if idle_sec_val < 5 and not is_dashboard:
            if active_process and active_process != "None" and active_process != "Paused":
                last_proc = shared_state.get("last_app_process")
                last_title = shared_state.get("last_app_title")
                accum_sec = shared_state.get("app_accumulated_seconds", 0)

                is_valid_title = bool(active_title and active_title not in ["None", "Paused"])
                title_changed = is_valid_title and (last_title is not None) and (active_title != last_title)

                if active_process == last_proc and not title_changed:
                    new_accum = accum_sec + 1
                    if is_valid_title:
                        shared_state["last_app_title"] = active_title
                    
                    # Periodically flush every 10 seconds so analytics update continuously and never get lost
                    if new_accum >= 10 and last_proc:
                        try:
                            target_flush_title = last_title if is_valid_title else active_title
                            db.log_app_usage(last_proc, target_flush_title, new_accum, wait=False)
                            shared_state["app_accumulated_seconds"] = 0
                        except Exception as e:
                            print(f"Error periodically flushing app usage: {e}")
                    else:
                        shared_state["app_accumulated_seconds"] = new_accum
                else:
                    # Application process OR window title changed: flush buffered usage for previous title
                    if last_proc and accum_sec > 0:
                        try:
                            db.log_app_usage(last_proc, last_title, accum_sec, wait=False)
                        except Exception as e:
                            print(f"Error logging app usage on switch: {e}")
                        
                        # 13 Cognitive Features: Log context switches in work mode ONLY when process name changes
                        if current_mode == "work" and last_proc and active_process and active_process != last_proc:
                            context_switch_deque.append(time.time())
                            try:
                                db.log_context_switch(last_proc, active_process, wait=False)
                            except Exception as e:
                                print(f"Error logging context switch: {e}")

                    shared_state["last_app_process"] = active_process
                    shared_state["last_app_title"] = active_title if is_valid_title else "None"
                    shared_state["app_accumulated_seconds"] = 1
        else:
            # User went idle, flush accumulated time to buffer and save/flush to DB
            last_proc = shared_state.get("last_app_process")
            last_title = shared_state.get("last_app_title")
            accum_sec = shared_state.get("app_accumulated_seconds", 0)
            if last_proc and accum_sec > 0:
                try:
                    db.log_app_usage(last_proc, last_title, accum_sec, wait=False)
                except Exception as e:
                    print(f"Error logging app usage on idle: {e}")
                shared_state["last_app_process"] = None
                shared_state["last_app_title"] = None
                shared_state["app_accumulated_seconds"] = 0
            
                # Explicitly commit app usage buffer to SQLite
                try:
                    db.save(wait=False)
                except Exception as e:
                    print(f"Error saving DB on idle transition: {e}")

        # Get settings from database dynamically (cached for 5s to reduce CPU wakeups and SQLite locks)
        now_sec = time.time()
        if not hasattr(main_state_machine, "_last_settings_fetch") or (now_sec - main_state_machine._last_settings_fetch >= 5.0) or last_settings is None:
            main_state_machine._last_settings_fetch = now_sec
            try:
                settings = db.get_settings()
                adaptive = db.get_adaptive_times()
            except Exception as e:
                print(f"Error loading settings/adaptive: {e}")
                settings = last_settings if last_settings else {"work_keywords": [], "recharge_keywords": [], "idle_timeout_seconds": 300, "custom_rules": []}
                adaptive = getattr(main_state_machine, "_cached_adaptive", {"work_minutes": 25, "rest_seconds": 300})
            main_state_machine._cached_settings = settings
            main_state_machine._cached_adaptive = adaptive
        else:
            settings = main_state_machine._cached_settings
            adaptive = main_state_machine._cached_adaptive

        if settings != last_settings:
            # Only invalidate if keywords changed
            if not last_settings or settings.get("work_keywords") != last_settings.get("work_keywords") or settings.get("recharge_keywords") != last_settings.get("recharge_keywords") or settings.get("custom_rules") != last_settings.get("custom_rules"):
                _safe_regex_cache.clear()
            last_classified_process = None
            last_classified_title = None
            last_settings = settings
            try:
                from backend.database import clear_regex_caches
                clear_regex_caches()
            except Exception:
                pass
            
        work_keywords = settings["work_keywords"]
        recharge_keywords = settings["recharge_keywords"]
        idle_limit = settings["idle_timeout_seconds"]
        work_limit_sec = adaptive["work_minutes"] * 60
        
        # 13 Cognitive Features: suggested work limits from morning readiness recovery score (cached for 60s)
        if now_sec - last_recovery_fetch_time >= 60.0 or cached_recovery_data is None:
            try:
                cached_recovery_data = db.get_recovery_score()
                last_recovery_fetch_time = now_sec
            except Exception as e:
                print(f"Error applying recovery score limits: {e}")
                
        if settings.get("adaptive_timers_enabled", True) and cached_recovery_data:
            work_limit_sec = cached_recovery_data.get("suggested_work_minutes", 25) * 60
            
        rest_limit_sec = adaptive["rest_seconds"]



        # Determine target mode
        target_mode = "neutral"
        if idle_sec_val >= idle_limit:
            target_mode = "rest"
        else:
            if active_process == last_classified_process and active_title == last_classified_title:
                target_mode = last_classified_mode
            else:
                target_mode = classify_activity_mode(
                    active_process, 
                    active_title, 
                    work_keywords, 
                    recharge_keywords, 
                    settings.get("custom_rules", []),
                    settings.get("neutral_keywords", [])
                )
                last_classified_process = active_process
                last_classified_title = active_title
                last_classified_mode = target_mode

        shared_state["active_category"] = target_mode

        # ╔══════════════════════════════════════════════════════════════════════╗
        # ║  MODE TRANSITION PIPELINE — Execution Order (every 1s tick)         ║
        # ║                                                                      ║
        # ║  1. CLASSIFY: target_mode = classify_activity_mode(active_window)    ║
        # ║  2. EXTERNAL SYNC: Check if UI/API set shared_state["current_mode"]  ║
        # ║     → If external change detected, adopt it + set 120s override lock ║
        # ║  3. TRANSITION GUARDS (evaluated in order, any can suppress):        ║
        # ║     a. Manual override lock: User clicked a mode button? Suppress    ║
        # ║        auto-transitions for 120s (idle→rest always allowed).         ║
        # ║     b. Distraction dwell: work→recharge held for 15-60s grace.       ║
        # ║  4. EXECUTE TRANSITION: Log session, reset flow/timers, swap files.  ║
        # ║                                                                      ║
        # ║  Data flow: UI → POST /api/set_mode → shared_state["current_mode"]  ║
        # ║             → Step 2 reads it → current_mode (local) updated         ║
        # ║             → Step 3 prevents classifier from reverting it           ║
        # ╚══════════════════════════════════════════════════════════════════════╝

        # ── Step 2: External Sync ─────────────────────────────────────────────
        # The Flask thread (POST /api/set_mode, POST /api/nudge/action) writes
        # to shared_state["current_mode"]. If it differs from our local
        # current_mode, the user (or a nudge action) requested a mode change.
        # We adopt it here and set a pinned override lock so the classifier (Step 1)
        # does not immediately revert the user's manual sprint choice.
        external_mode = shared_state.get("current_mode")
        if external_mode and external_mode != current_mode:
            print(f"[State Machine] External mode transition detected: {current_mode} -> {external_mode}")
            current_mode, state_start_time, is_flow_session, flow_start_time, work_consecutive_seconds = \
                _execute_mode_transition(
                    prev_mode=current_mode,
                    new_mode=external_mode,
                    state_start_time=state_start_time,
                    is_flow_session=is_flow_session,
                    flow_start_time=flow_start_time,
                    idle_limit=idle_limit,
                    is_idle_transition=False,
                    db=db, shared_state=shared_state, nudge_state=nudge_state,
                    workspace_mgr=workspace_mgr, battery=battery
                )
            # Lock out automatic classification for 120s or until unpinned
            nudge_state["manual_override_until"] = now_sec + 120.0
            if shared_state.get("pinned_mode"):
                shared_state["pinned_mode"] = external_mode

        # ── Step 3: Transition Guards ─────────────────────────────────────────
        should_transition = (target_mode != current_mode)

        # Guard 3a: Manual override & Pinned Mode lock (UI-initiated mode changes stick)
        # Only idle→rest bypasses this lock (user shouldn't be stuck if they walk away)
        pinned = shared_state.get("pinned_mode")
        manual_override_active = (pinned is not None and pinned == current_mode) or (now_sec < nudge_state.get("manual_override_until", 0.0))
        if should_transition and manual_override_active and target_mode != "rest":
            should_transition = False

        # Guard 3b: Distraction dwell grace period (work→recharge only)
        # Prevents instant mode flip when briefly opening YouTube during a work sprint.
        # Grace period: strict=15s, balanced=30s, gentle=60s
        if should_transition and current_mode == "work" and target_mode == "recharge" and settings.get("enable_distraction_nudges", True):
            proactivity = settings.get("proactivity_level", "balanced")
            if proactivity != "disabled":
                dwell_thresh = 15.0 if proactivity == "strict" else (60.0 if proactivity == "gentle" else 30.0)
                dwell_start = nudge_state.get("distraction_dwell_start")
                if dwell_start is None:
                    nudge_state["distraction_dwell_start"] = now_sec
                    should_transition = False
                elif (now_sec - dwell_start) < dwell_thresh:
                    should_transition = False
                else:
                    nudge_state["distraction_dwell_start"] = None
        elif target_mode != "recharge" or current_mode != "work":
            if nudge_state.get("distraction_dwell_start") is not None:
                nudge_state["distraction_dwell_start"] = None

        # ── Step 4: Execute Transition ────────────────────────────────────────
        if should_transition:
            print(f"State transition: {current_mode} -> {target_mode}")
            current_mode, state_start_time, is_flow_session, flow_start_time, work_consecutive_seconds = \
                _execute_mode_transition(
                    prev_mode=current_mode,
                    new_mode=target_mode,
                    state_start_time=state_start_time,
                    is_flow_session=is_flow_session,
                    flow_start_time=flow_start_time,
                    idle_limit=idle_limit,
                    is_idle_transition=(target_mode == "rest"),
                    db=db, shared_state=shared_state, nudge_state=nudge_state,
                    workspace_mgr=workspace_mgr, battery=battery
                )
            try:
                db.flush_battery_state(battery.capacity, battery.consecutive_work_minutes, wait=False)
                db.save(wait=False)
            except Exception as e:
                print(f"Error flushing database on transition: {e}")
        else:
            elapsed = (datetime.now() - state_start_time).total_seconds()
            shared_state["elapsed_seconds"] = int(elapsed)

            effective_work_limit = work_limit_sec + (shared_state.get("session_extension_seconds", 0) or 0)
            if current_mode == "work" and elapsed >= (effective_work_limit + 60.0):
                # Work sprint exceeded limit — force transition to neutral
                # Note: We use _execute_mode_transition which logs the session normally,
                # but we also want a special brain_dump note, so log separately here.
                is_flow_final = False
                flow_dur = 0.0
                if is_flow_session:
                    is_flow_final = True
                    if flow_start_time:
                        flow_dur = max(0.0, (datetime.now() - flow_start_time).total_seconds())

                db.log_session("work", state_start_time, datetime.now(), brain_dump="[End] Focus limit reached", bypassed=False, is_flow=is_flow_final, flow_duration=flow_dur, wait=False)

                is_flow_session = False
                flow_start_time = None
                work_consecutive_seconds = 0
                shared_state["session_extension_seconds"] = 0

                current_mode = "neutral"
                shared_state["current_mode"] = current_mode
                state_start_time = datetime.now()
                shared_state["elapsed_seconds"] = 0



        # 13 Cognitive Features: Flow State Detection Heuristic
        if current_mode == "work" and idle_sec_val < 5:
            work_consecutive_seconds += 1
            if work_consecutive_seconds >= 900 and not is_flow_session:
                is_flow_session = True
                from datetime import timedelta
                flow_start_time = datetime.now() - timedelta(seconds=900)
                print("Autopilot: Deep Flow state detected! Sustained focus for 15+ minutes.")
        elif idle_sec_val >= 60:
            work_consecutive_seconds = 0

        # Update Battery Math (In-Memory)
        try:
            is_active_work = (current_mode == "work")
            current_cap, current_streak = battery.process_tick(
                is_working=is_active_work,
                elapsed_minutes=tick_duration_minutes,
                mode=current_mode
            )
            shared_state['battery_capacity'] = current_cap
            shared_state['battery_consecutive_work'] = current_streak
            
            # Flush to DB every 300 seconds (5 minutes) as a backup safety save
            ticks_since_flush += 1
            if ticks_since_flush >= 300:
                try:
                    db.flush_battery_state(battery.capacity, battery.consecutive_work_minutes, wait=False)
                    db.save(wait=False)
                except Exception:
                    pass
                ticks_since_flush = 0
        except Exception as e:
            print(f"Error in CognitiveBattery tick: {e}")

        # Proactive Cognitive Companion: In-memory nudge & intervention engine
        try:
            evaluate_proactive_nudges(
                current_mode=current_mode,
                target_mode=target_mode,
                active_process=active_process,
                active_title=active_title,
                elapsed_seconds=shared_state.get("elapsed_seconds", 0),
                work_limit_sec=work_limit_sec,
                battery_cap=shared_state.get("battery_capacity", 100.0),
                is_flow_session=is_flow_session,
                idle_sec_val=idle_sec_val,
                settings=settings,
                context_switch_deque=context_switch_deque,
                nudge_state=nudge_state,
                shared_state=shared_state
            )
        except Exception as e:
            print(f"Error evaluating proactive nudges: {e}")

        try:
            db.close_thread_connection()
        except Exception:
            pass

def run_webview_gui(url):
    """Run a standalone pywebview Edge WebView2 window."""
    import webview
    import psutil
    import os
    import sys
    import threading
    
    # Configure WEBVIEW2_RUNTIME_PATH dynamically if needed
    is_webview2_installed()
    
    # 1. Parent process monitor thread
    def monitor_parent():
        parent_pid = os.getppid()
        try:
            parent = psutil.Process(parent_pid)
        except Exception:
            close_log_handles()
            os._exit(0)

        while True:
            time.sleep(1.0)
            try:
                if not parent.is_running() or parent.status() == psutil.STATUS_ZOMBIE:
                    close_log_handles()
                    os._exit(0)
            except Exception:
                close_log_handles()
                os._exit(0)
                
    monitor_thread = threading.Thread(target=monitor_parent, daemon=True)
    monitor_thread.start()
    
    # 2. Start recurring background EcoQoS disabling for child processes (Edge WebView2)
    disable_ecoqos_for_process_tree()

            
    # 3. WebView window setup
    # Set background color to #0b0f19 to avoid white flash
    webview.create_window(
        "MIND-FLOW // Cognitive Companion Dashboard",
        url,
        width=1280,
        height=800,
        background_color="#0b0f19"
    )
    is_debug = os.getenv("MINDFLOW_DEBUG", "0") == "1"
    webview.start(gui='edgechromium', debug=is_debug)

def launch_app_window(port):
    """Launch the dashboard url in a standalone pywebview GUI subprocess."""
    from backend.server import SHARED_API_TOKEN
    
    env = os.environ.copy()
    env["MIND_FLOW_TOKEN"] = SHARED_API_TOKEN
    env["MINDFLOW_DUCKDB_FILE"] = ":memory:"
    
    if getattr(sys, 'frozen', False):
        exe = sys.executable
        try:
            return subprocess.Popen([exe, "--gui", str(port)], env=env)
        except Exception as e:
            print(f"Error launching standalone app GUI: {e}")
            return None
    else:
        exe = sys.executable
        script = sys.argv[0]
        try:
            return subprocess.Popen([exe, script, "--gui", str(port)], env=env)
        except Exception as e:
            print(f"Error launching standalone app GUI in dev: {e}")
            return None

def is_webview2_installed():
    if sys.platform != "win32":
        return True
    try:
        import webview
    except ImportError:
        return False
    registry_found = False
    try:
        import winreg
        paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}")
        ]
        for root, subkey in paths:
            try:
                with winreg.OpenKey(root, subkey) as key:
                    version, _ = winreg.QueryValueEx(key, "pv")
                    if version and version != "0.0.0.0":
                        registry_found = True
                        break
            except FileNotFoundError:
                continue
    except Exception:
        pass
        
    if registry_found:
        return True

    # Robust path-based check fallback for systems where Edge Update keys are missing
    import glob
    search_roots = []
    pf_x86 = os.environ.get("ProgramFiles(x86)")
    pf_x64 = os.environ.get("ProgramFiles")
    sys_drive = os.environ.get("SystemDrive", "C:")
    
    if pf_x86:
        search_roots.append(os.path.join(pf_x86, "Microsoft", "EdgeWebView", "Application"))
    else:
        search_roots.append(os.path.join(sys_drive + "\\Program Files (x86)", "Microsoft", "EdgeWebView", "Application"))
        
    if pf_x64:
        search_roots.append(os.path.join(pf_x64, "Microsoft", "EdgeWebView", "Application"))
    else:
        search_roots.append(os.path.join(sys_drive + "\\Program Files", "Microsoft", "EdgeWebView", "Application"))

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        search_roots.append(os.path.join(local_appdata, "Microsoft", "EdgeWebView", "Application"))
        
    for root in search_roots:
        if os.path.exists(root):
            try:
                matches = glob.glob(os.path.join(root, "**", "msedgewebview2.exe"), recursive=True)
                if matches:
                    runtime_dir = os.path.dirname(matches[0])
                    try:
                        import webview
                        webview.settings['WEBVIEW2_RUNTIME_PATH'] = runtime_dir
                    except Exception:
                        pass
                    return True
            except Exception:
                pass
    return False

import signal
def sigterm_handler(signum, frame):
    print("SIGTERM received, flushing db...")
    try:
        db.flush_queue()
        db.close()
    except Exception as e:
        print(f"Error flushing db on SIGTERM: {e}")
    sys.exit(0)

signal.signal(signal.SIGTERM, sigterm_handler)

if __name__ == "__main__":
    if sys.platform == "win32":
        assign_self_to_job()

    try:
        disable_ecoqos_for_process_tree()
    except Exception:
        pass



    # If --gui argument is passed, launch the pywebview standalone window process
    if len(sys.argv) > 1 and sys.argv[1] == "--gui":
        port = sys.argv[2] if len(sys.argv) > 2 else "5000"
        token = os.environ.get("MIND_FLOW_TOKEN", "")
        run_webview_gui(f"http://127.0.0.1:{port}/?token={token}")
        try:
            db.flush_queue()
        except Exception:
            pass
        sys.exit(0)

    # Enforce single-instance execution on Windows (prevent multiple concurrent app.py processes)
    _single_instance_mutex = None
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            ERROR_ALREADY_EXISTS = 183
            _single_instance_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\MIND_FLOW_SINGLE_INSTANCE_MUTEX")
            if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
                print("[MIND-FLOW] An active instance of MIND-FLOW is already running.")
                hwnd = ctypes.windll.user32.FindWindowW(None, "MIND-FLOW // Cognitive Companion Dashboard")
                if not hwnd:
                    hwnd = ctypes.windll.user32.FindWindowW(None, "MIND-FLOW // Cognitive Companion")
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                sys.exit(0)
        except Exception as e:
            print(f"[MIND-FLOW] Single-instance mutex check error: {e}")

    # 1. Start Server in a separate daemon thread
    port = get_free_port()
    shared_state["server_port"] = port
    server_thread = threading.Thread(target=run_server, kwargs={"port": port}, daemon=True)
    server_thread.start()
    
    # Wait a brief moment for Flask to initialize
    time.sleep(0.5)
    
    # Print token and port for headless test scripts to capture
    print(f"API Token: {SHARED_API_TOKEN}")
    print(f"Server Port: {port}")

    # 2. Open dashboard in native app window (pywebview process) or default browser fallback
    if sys.platform == "win32" and not is_webview2_installed():
        print("\n[MIND-FLOW] Microsoft Edge WebView2 Runtime is not installed.")
        print("To run in a standalone application window, please install it from:")
        print("https://developer.microsoft.com/en-us/microsoft-edge/webview2/\n")
        print("Launching the dashboard in your default web browser instead...")
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{port}/?token={SHARED_API_TOKEN}")
        gui_proc = None
    else:
        print("Launching Cognitive Dashboard in Standalone App Mode...")
        gui_proc = launch_app_window(port)

    # 3. Start state machine in the main thread (blocks execution)
    try:
        main_state_machine(gui_process=gui_proc)
    except KeyboardInterrupt:
        print("\nMIND-FLOW terminated by user.")
        try:
            db.flush_queue()
            db.close()
        except Exception as e:
            print(f"Error flushing db on exit: {e}")
        sys.exit(0)
