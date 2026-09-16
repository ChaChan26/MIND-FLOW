"""
MIND-FLOW Local Flask API Server.
Provides secure IPC endpoints for telemetry, state control, and frontend dashboard integration.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import time
import copy
import socket
import ipaddress
import urllib.request
import re
from functools import wraps
from datetime import datetime, date, timedelta
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, request, send_from_directory, make_response, redirect
import logging
logger = logging.getLogger('server')

try:
    import psutil
except ImportError:
    psutil = None

from backend.thread_pools import workspace_executor as _workspace_executor

_proc_cache = None
def get_current_process():
    global _proc_cache
    if _proc_cache is None and psutil is not None:
        try:
            _proc_cache = psutil.Process()
        except Exception:
            pass
    return _proc_cache

def require_local_origin(f):
    """CSRF protection: reject POST requests from foreign Origins."""
    @wraps(f)
    def decorated(*args, **kwargs):
        origin = request.headers.get('Origin', '')
        referer = request.headers.get('Referer', '')
        allowed_hosts = {'127.0.0.1', 'localhost', '::1', '[::1]', '::ffff:127.0.0.1'}
        
        if origin:
            try:
                url_to_parse = origin if '://' in origin else f'http://{origin}'
                parsed = urlparse(url_to_parse)
                hostname = parsed.hostname
                if hostname:
                    hostname = hostname.lower()
                if hostname not in allowed_hosts:
                    return jsonify({"error": "Forbidden: invalid origin"}), 403
            except Exception:
                return jsonify({"error": "Forbidden: invalid origin"}), 403
                
        if referer and not origin:
            try:
                url_to_parse = referer if '://' in referer else f'http://{referer}'
                parsed = urlparse(url_to_parse)
                hostname = parsed.hostname
                if hostname:
                    hostname = hostname.lower()
                if hostname not in allowed_hosts:
                    return jsonify({"error": "Forbidden: invalid referer origin"}), 403
            except Exception:
                return jsonify({"error": "Forbidden: invalid referer origin"}), 403
                
        if not origin and not referer:
            # If both are missing, ensure request is strictly local
            remote = request.remote_addr
            if remote not in {'127.0.0.1', '::1', '::ffff:127.0.0.1'}:
                return jsonify({"error": "Forbidden: missing origin/referer verification"}), 403

        return f(*args, **kwargs)
    return decorated

import os
import json
import secrets
from backend.database import DEFAULT_DATA_DIR

def get_or_create_persistent_token():
    token_file = os.path.join(DEFAULT_DATA_DIR, "api_token.json")
    if os.path.exists(token_file):
        try:
            with open(token_file, "r") as f:
                return json.load(f).get("token") or secrets.token_hex(16)
        except Exception:
            pass
    token = secrets.token_hex(16)
    try:
        with open(token_file, "w") as f:
            json.dump({"token": token}, f)
    except Exception:
        pass
    return token

SHARED_API_TOKEN = get_or_create_persistent_token()

def require_api_token(f):
    """API token validation decorator to protect backend from unauthorized local calls."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-MIND-FLOW-TOKEN")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        
        if not token:
            token = request.cookies.get("MIND_FLOW_TOKEN")

        if not token:
            token = request.args.get("token")
        
        if not token or not secrets.compare_digest(token, SHARED_API_TOKEN):
            return jsonify({"error": "Unauthorized: invalid or missing API token"}), 401
        return f(*args, **kwargs)
    return decorated

# Adjust path to import from parent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database import MindFlowDB, matches_keyword, get_default_data_dir, matches_any_keyword, is_browser_process

def get_resource_path(relative_path):
    """ Get absolute path to resource, prioritizing local disk paths before PyInstaller bundled ones """
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.abspath(os.path.dirname(sys.executable))
        parent_dir = os.path.abspath(os.path.join(exe_dir, ".."))
        
        # Check parent folder, executable folder, or portable data folder
        for base in [parent_dir, exe_dir, get_default_data_dir()]:
            local_path = os.path.join(base, relative_path)
            if os.path.exists(local_path):
                return local_path
                
        # Fallback to the temp folder where PyInstaller extracted files
        try:
            return os.path.join(sys._MEIPASS, relative_path)
        except AttributeError:
            pass
            
    # Dev mode: use relative path from backend directory
    base_path = os.path.abspath(os.path.dirname(__file__))
    base_path = os.path.abspath(os.path.join(base_path, ".."))
    return os.path.join(base_path, relative_path)

app = Flask(__name__, 
            static_folder=get_resource_path("static"), 
            template_folder=get_resource_path("templates"))
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Initialize database
db = MindFlowDB()

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.close_thread_connection()

@app.before_request
def validate_host():
    """Verify that the Host header is strictly local to prevent DNS Rebinding."""
    host = request.host
    if not host:
        # Fallback to remote_addr if Host is missing (e.g. some internal tests)
        remote = request.remote_addr
        if not remote or remote not in {'127.0.0.1', '::1', '::ffff:127.0.0.1'}:
            return jsonify({"error": "Forbidden: Missing Host header"}), 400
        return
    
    if ']' in host:
        hostname = host.split(']')[0] + ']'
    else:
        hostname = host.split(':')[0]
    hostname = hostname.lower()
    if hostname not in {'localhost', '127.0.0.1', '[::1]'}:
        return jsonify({"error": "Forbidden: Invalid Host header"}), 403

@app.after_request
def disable_caching_and_set_cors(response):
    """Disable caching for all responses and set strict local CORS headers."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    origin = request.headers.get("Origin")
    if origin in ["http://localhost:5000", "http://127.0.0.1:5000", "http://localhost:5173", "http://127.0.0.1:5173"]:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-MIND-FLOW-TOKEN"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        
    return response

import threading
import copy

class StandardDictWrapper(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.RLock()

    def get_snapshot(self):
        with self._lock:
            return {k: v for k, v in self.items()}

    def update_key(self, key, func, default=None):
        """Atomically mutate a dictionary key under thread lock using a transformer function."""
        with self._lock:
            val = super().get(key, default)
            new_val = func(val)
            super().__setitem__(key, new_val)
            return new_val

    def __setitem__(self, key, value):
        with self._lock:
            super().__setitem__(key, value)

    def __getitem__(self, key):
        with self._lock:
            return super().__getitem__(key)

    def get(self, key, default=None):
        with self._lock:
            return super().get(key, default)

    def pop(self, key, *args):
        with self._lock:
            return super().pop(key, *args)

    def popitem(self):
        with self._lock:
            return super().popitem()

    def setdefault(self, key, default=None):
        with self._lock:
            return super().setdefault(key, default)

    def clear(self):
        with self._lock:
            super().clear()

    def update(self, *args, **kwargs):
        with self._lock:
            super().update(*args, **kwargs)

    def __delitem__(self, key):
        with self._lock:
            super().__delitem__(key)

    def __contains__(self, key):
        with self._lock:
            return super().__contains__(key)

    def __len__(self):
        with self._lock:
            return super().__len__()

    def keys(self):
        with self._lock:
            return list(super().keys())

    def values(self):
        with self._lock:
            return list(super().values())

    def items(self):
        with self._lock:
            return list(super().items())

# In-memory shared state between Flask thread and Background Watcher thread
shared_state = StandardDictWrapper({
    "current_mode": "neutral",
    "active_category": "neutral",
    "active_window_title": "Detecting...",
    "active_process_name": "Detecting...",
    "elapsed_seconds": 0,
    "idle_seconds": 0,
    "tracking_active": True,
    "mode_start_time": None,
    "last_lockout_time": None,
    "last_external_window": "None",
    "last_external_process": "None",
    "last_app_process": None,
    "last_app_title": None,
    "app_accumulated_seconds": 0,
    "battery_capacity": 100.0,
    "battery_consecutive_work": 0.0,
    "active_nudge": None,
    "nudge_snooze_until": 0.0,
    "session_extension_seconds": 0
})

# In-memory cache for weekly analytics endpoint responses
_analytics_cache = {}
_analytics_cache_date = None
_analytics_cache_lock = threading.Lock()

def clear_server_analytics_cache():
    """Clear server-side in-memory analytics cache."""
    with _analytics_cache_lock:
        _analytics_cache.clear()

try:
    from backend.database import register_cache_invalidation_listener
    register_cache_invalidation_listener(clear_server_analytics_cache)
except Exception:
    pass


@app.route("/auth", methods=["POST"])
@require_local_origin
def auth():
    token = request.form.get("token")
    if token and secrets.compare_digest(token, SHARED_API_TOKEN):
        from flask import make_response, redirect
        response = make_response(redirect("/"))
        response.set_cookie("MIND_FLOW_TOKEN", token, httponly=True, samesite="Lax")
        return response
    return "Unauthorized", 401

@app.route("/")
def index():
    from flask import make_response, send_from_directory
    response = make_response(send_from_directory(app.template_folder, "index.html"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    token = request.args.get("token")
    if token and secrets.compare_digest(token, SHARED_API_TOKEN):
        response.set_cookie("MIND_FLOW_TOKEN", token, httponly=True, samesite="Lax")
    return response

@app.route("/api/status", methods=["GET"])
@require_api_token
def get_status():
    settings = db.get_settings()
    adaptive = db.get_adaptive_times()
    adaptive_work_limit_seconds = adaptive["work_minutes"] * 60
    adaptive_rest_limit_seconds = adaptive["rest_seconds"]
    adaptive_reason = adaptive["reason"]
    work_limit_seconds = settings["work_duration_minutes"] * 60
    
    # Retrieve base cached status data
    stats = db.get_cached_status_data()
    
    # Snapshot of shared state
    state = shared_state.get_snapshot()
    
    # Read in-memory battery capacity and map to 1-5 scale for backward compatibility
    battery_cap = state.get('battery_capacity', 100.0)
    current_energy = max(1.0, min(5.0, battery_cap / 20.0))
    
    high_stress_alert = stats["high_stress_alert"]
    latest_mood = stats["latest_mood"]
    today_work = stats["today_work_seconds"]
    today_recharge = stats["today_recharge_seconds"]
    today_rest = stats["today_rest_seconds"]
    today_bypasses = stats["today_bypasses"]
    forecast_message = stats["forecast_fatigue_alert"]
    circadian_forecast = stats.get("circadian_forecast")

    if high_stress_alert:
        adaptive_rest_limit_seconds = max(120, adaptive_rest_limit_seconds * 2)
        
    # Add ongoing sessions to the totals in real-time
    cur_mode = state["current_mode"]
    elapsed = state["elapsed_seconds"]
    idle = state["idle_seconds"]
    
    if cur_mode == "work":
        today_work += elapsed
    elif cur_mode == "recharge":
        today_recharge += elapsed
    elif cur_mode == "rest":
        today_rest += elapsed
        
    # Dynamic companion advice generation with CBT mental health interventions
    from backend.companion_service import generate_companion_message, calculate_battery_forecast
    companion_message = generate_companion_message(
        tracking_active=state["tracking_active"],
        today_bypasses=today_bypasses,
        high_stress_alert=high_stress_alert,
        latest_mood=latest_mood,
        current_energy=battery_cap,
        cur_mode=cur_mode
    )

    # Calculate battery forecast & circadian check
    forecast_message = calculate_battery_forecast(
        cur_mode=cur_mode,
        battery_cap=battery_cap,
        adaptive_rest_limit_seconds=adaptive_rest_limit_seconds,
        base_alert_message=forecast_message
    )

    # 13 Cognitive Features: status calculations
    recovery_data = db.get_recovery_score()
    streak_info = db.get_streak_info()
    focus_score = db.calculate_focus_score()

    return jsonify({
        "current_mode": cur_mode,
        "active_category": state.get("active_category", cur_mode if cur_mode in ["work", "recharge"] else "neutral"),
        "category": state.get("active_category", cur_mode if cur_mode in ["work", "recharge"] else "neutral"),
        "active_window_title": state["active_window_title"],
        "active_process_name": state["active_process_name"],
        "elapsed_seconds": elapsed,
        "work_limit_seconds": work_limit_seconds,
        "adaptive_work_limit_seconds": adaptive_work_limit_seconds,
        "adaptive_rest_limit_seconds": adaptive_rest_limit_seconds,
        "adaptive_reason": adaptive_reason,
        "idle_seconds": idle,
        "tracking_active": state["tracking_active"],
        "current_energy": round(current_energy, 2),
        "battery_capacity": round(battery_cap, 2),
        "consecutive_work_minutes": round(state.get('battery_consecutive_work', 0.0), 2),
        "today_work_seconds": int(today_work),
        "today_recharge_seconds": int(today_recharge),
        "today_rest_seconds": int(today_rest),
        "today_bypasses": today_bypasses,
        "companion_message": companion_message,
        "last_external_window": state["last_external_window"],
        "last_external_process": state["last_external_process"],
        "current_goal": db.get_current_goal(),
        "hydration": db.get_hydration(),
        "forecast_message": forecast_message,
        "high_stress_alert": high_stress_alert,
        "latest_mood": latest_mood,
        "circadian_forecast": circadian_forecast,
        "focus_score": focus_score,
        "recovery_score": recovery_data["recovery_score"],
        "suggested_work_minutes": recovery_data["suggested_work_minutes"],
        "streak_days": streak_info["current_streak"],
        "longest_streak_days": streak_info["longest_streak"],
        "is_cloud_sync": settings.get("is_cloud_sync", False),
        "active_nudge": state.get("active_nudge", None),
        "session_extension_seconds": state.get("session_extension_seconds", 0),
        "nudge_snooze_until": state.get("nudge_snooze_until", 0.0),
        "settings": {
            "enable_audio_chimes": settings.get("enable_audio_chimes", True),
            "enable_desktop_toasts": settings.get("enable_desktop_toasts", True),
            "proactivity_level": settings.get("proactivity_level", "balanced"),
            "enable_eyecare_nudges": settings.get("enable_eyecare_nudges", True),
            "enable_hydration_nudges": settings.get("enable_hydration_nudges", True),
            "enable_distraction_nudges": settings.get("enable_distraction_nudges", True),
            "enable_thrashing_nudges": settings.get("enable_thrashing_nudges", True)
        }
    })

@app.route("/api/status/toggle", methods=["POST"])
@require_local_origin
@require_api_token
def toggle_tracking():
    data = request.get_json(silent=True) or {}
    enable = data.get("enable", not shared_state["tracking_active"])
    shared_state["tracking_active"] = enable
    return jsonify({"tracking_active": shared_state["tracking_active"]})


@app.route("/api/set_mode", methods=["POST"])
@require_local_origin
@require_api_token
def set_mode():
    data = request.get_json(silent=True) or {}
    new_mode = data.get("mode")
    valid_modes = {"work", "recharge", "rest", "neutral"}
    if not new_mode or new_mode not in valid_modes:
        return jsonify({"error": "Invalid or missing mode parameter"}), 400

    old_mode = shared_state.get("current_mode", "neutral")
    if old_mode != new_mode:
        shared_state["current_mode"] = new_mode
        shared_state["elapsed_seconds"] = 0
        shared_state["mode_start_time"] = datetime.now()

        try:
            from backend.workspace_manager import WorkspaceManager
            from backend.database import get_default_data_dir
            workspace_mgr = WorkspaceManager(get_default_data_dir())
            _workspace_executor.submit(workspace_mgr.transition_workspace, old_mode, new_mode)
        except Exception:
            pass

    return jsonify({"status": "success", "current_mode": shared_state["current_mode"]})

@app.route("/api/nudge/action", methods=["POST"])
@require_local_origin
@require_api_token
def handle_nudge_action():
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    nudge_id = data.get("nudge_id")
    
    if not action:
        return jsonify({"error": "Missing action parameter"}), 400
        
    old_mode = shared_state.get("current_mode", "neutral")
    
    if action == "take_break":
        # Transition mode to rest and clear active nudge
        shared_state["current_mode"] = "rest"
        shared_state["elapsed_seconds"] = 0
        shared_state["mode_start_time"] = datetime.now()
        shared_state["session_extension_seconds"] = 0
        shared_state["active_nudge"] = None
        
        try:
            from backend.workspace_manager import WorkspaceManager
            from backend.database import get_default_data_dir
            workspace_mgr = WorkspaceManager(get_default_data_dir())
            _workspace_executor.submit(workspace_mgr.transition_workspace, old_mode, "rest")
        except Exception:
            pass

    elif action == "switch_to_recharge":
        # Transition mode to recharge and clear active nudge
        shared_state["current_mode"] = "recharge"
        shared_state["elapsed_seconds"] = 0
        shared_state["mode_start_time"] = datetime.now()
        shared_state["session_extension_seconds"] = 0
        shared_state["active_nudge"] = None
        
        try:
            from backend.workspace_manager import WorkspaceManager
            from backend.database import get_default_data_dir
            workspace_mgr = WorkspaceManager(get_default_data_dir())
            _workspace_executor.submit(workspace_mgr.transition_workspace, old_mode, "recharge")
        except Exception:
            pass

    elif action in ["start_focus", "start_work"]:
        # Transition mode to work and start fresh focus sprint
        shared_state["current_mode"] = "work"
        shared_state["elapsed_seconds"] = 0
        shared_state["mode_start_time"] = datetime.now()
        shared_state["session_extension_seconds"] = 0
        shared_state["active_nudge"] = None
        
        try:
            from backend.workspace_manager import WorkspaceManager
            from backend.database import get_default_data_dir
            workspace_mgr = WorkspaceManager(get_default_data_dir())
            _workspace_executor.submit(workspace_mgr.transition_workspace, old_mode, "work")
        except Exception:
            pass

    elif action in ["reset_timer", "restart_focus"]:
        shared_state["elapsed_seconds"] = 0
        shared_state["mode_start_time"] = datetime.now()
        shared_state["session_extension_seconds"] = 0
        shared_state["active_nudge"] = None
            
    elif action == "drink_water":
        try:
            db.increment_hydration()
        except Exception as e:
            print(f"Error incrementing hydration on nudge action: {e}")
        shared_state["active_nudge"] = None
        
    elif action in ["extend_5m", "extend_focus"]:
        # Extend focus session by 300 seconds (capped at 1800s / 30m)
        shared_state.update_key("session_extension_seconds", lambda x: min(1800, (x or 0) + 300))
        shared_state["active_nudge"] = None

    elif action in ["extend_2m", "extend_break"]:
        # Extend break session by 120 seconds (capped at 600s / 10m)
        shared_state.update_key("session_extension_seconds", lambda x: min(600, (x or 0) + 120))
        shared_state["active_nudge"] = None
        
    elif action == "snooze":
        # Snooze all non-critical nudges for 15 minutes (900 seconds)
        shared_state["nudge_snooze_until"] = time.time() + 900.0
        shared_state["active_nudge"] = None
        
    elif action == "dismiss":
        shared_state["active_nudge"] = None
        
    else:
        return jsonify({"error": f"Unknown action '{action}'"}), 400
        
    return jsonify({
        "status": "success",
        "action": action,
        "active_nudge": shared_state.get("active_nudge"),
        "current_mode": shared_state.get("current_mode"),
        "session_extension_seconds": shared_state.get("session_extension_seconds", 0)
    })



@app.route("/api/settings", methods=["GET", "POST"])
@require_local_origin
@require_api_token
def manage_settings():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid payload"}), 400
        if len(str(data)) > 10000:
            return jsonify({"error": "Payload too large"}), 400
        db.update_settings(data)
        with _analytics_cache_lock:
            _analytics_cache.clear()
        return jsonify({"status": "success", "settings": db.get_settings()})
    else:
        return jsonify(db.get_settings())

@app.route("/api/goal", methods=["GET", "POST"])
@require_local_origin
@require_api_token
def manage_goal():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        goal = data.get("goal", "")
        db.set_current_goal(goal)
        return jsonify({"status": "success", "goal": db.get_current_goal()})
    else:
        return jsonify({"goal": db.get_current_goal()})



@app.route("/api/hydration", methods=["GET", "POST"])
@require_local_origin
@require_api_token
def manage_hydration():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}

        
        # SAFETY: Reject malformed or invalid JSON payloads when content is sent.
        # If the body is completely empty, we allow it to fall through to the default "+1 increment" path.
        raw_data = request.get_data()
        if raw_data and (not data or (data.get("cups") is None and data.get("delta") is None)):
            return jsonify({"error": "Missing 'cups' or 'delta' in payload", "hydration": db.get_hydration()}), 400
        
        cups = data.get("cups")
        delta = data.get("delta")
        if delta is not None:
            try:
                delta_val = float(delta)
                current_amount = db.get_hydration()["cups"]
                new_amount = max(0, float(current_amount) + delta_val)
                res = db.increment_hydration(cups=new_amount)

            except (ValueError, TypeError):
                return jsonify({"error": "Invalid numeric value for delta", "hydration": db.get_hydration()}), 400
        else:
            res = db.increment_hydration(cups=cups)

        return jsonify({"status": "success", "hydration": res})
    else:
        return jsonify(db.get_hydration())

@app.route("/api/reflections", methods=["GET", "POST"])
@require_local_origin
@require_api_token
def manage_reflections():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        energy = data.get("energy_level")
        friction = data.get("friction_level")
        summary = data.get("summary", "")
        mood = data.get("mood")
        sleep_hours = data.get("sleep_hours")
        sleep_quality = data.get("sleep_quality")
        
        if energy is None or friction is None:
            return jsonify({"error": "energy_level and friction_level are required"}), 400
        
        # Validate and clamp input ranges
        try:
            energy = max(1, min(5, int(energy)))
            friction = max(1, min(5, int(friction)))
        except (ValueError, TypeError):
            return jsonify({"error": "energy_level and friction_level must be integers 1-5"}), 400
        summary = str(summary).strip()[:500]  # Cap summary length
        
        validated_mood = None
        if mood:
            mood_str = str(mood).strip()
            mood_map = {m.lower(): m for m in ["Calm", "Focused", "Anxious", "Overwhelmed", "Frustrated", "Exhausted", "Neutral"]}
            validated_mood = mood_map.get(mood_str.lower(), None)
            
        validated_sleep_hours = None
        if sleep_hours is not None:
            try:
                validated_sleep_hours = max(0.0, min(24.0, float(sleep_hours)))
            except (ValueError, TypeError):
                return jsonify({"error": "sleep_hours must be a number between 0 and 24"}), 400
                
        validated_sleep_quality = None
        if sleep_quality is not None:
            try:
                validated_sleep_quality = max(1, min(5, int(sleep_quality)))
            except (ValueError, TypeError):
                return jsonify({"error": "sleep_quality must be an integer 1-5"}), 400
            
        entry = db.add_reflection(
            energy, friction, summary, 
            mood=validated_mood, 
            sleep_hours=validated_sleep_hours, 
            sleep_quality=validated_sleep_quality
        )
        
        # 13 Cognitive Features: Cognitive Distortion Detection (CBT)
        distortion_warning = None
        distortion_type = None
        summary_lower = summary.lower()
        if friction >= 4 or (validated_mood and validated_mood.lower() in ["anxious", "overwhelmed", "frustrated", "exhausted"]):
            all_or_nothing_kw = ["never", "always", "ruined", "useless", "failure", "completely", "impossible", "nothing"]
            catastrophizing_kw = ["disaster", "terrible", "horrible", "can't handle", "worst", "fail", "ruin", "destroy"]
            should_kw = ["should", "must", "ought to", "have to", "need to"]
            emotional_kw = ["feel like", "i feel", "feels bad", "feels wrong", "i'm sure"]
            
            if any(w in summary_lower for w in all_or_nothing_kw):
                distortion_type = "All-or-Nothing Thinking"
                distortion_warning = "Recognized All-or-Nothing thinking! It's rare for things to be 100% good or bad. Even when a feature has bugs, your progress is still real."
            elif any(w in summary_lower for w in catastrophizing_kw):
                distortion_type = "Catastrophizing"
                distortion_warning = "Catastrophizing detected! This challenge feels huge right now, but you have solved complex bugs before. Break it into micro-tasks."
            elif any(w in summary_lower for w in should_kw):
                distortion_type = "Should Statement"
                distortion_warning = "Spotted a 'Should' statement! Unrealistic expectations generate stress. Focus on what you *can* do, not what you *should* have done."
            elif any(w in summary_lower for w in emotional_kw):
                distortion_type = "Emotional Reasoning"
                distortion_warning = "Emotional reasoning detected! Feeling stuck doesn't mean you *are* stuck. Emotions are signals, not absolute facts."

        return jsonify({
            "status": "success", 
            "reflection": entry,
            "distortion_type": distortion_type,
            "distortion_warning": distortion_warning
        })
    else:
        return jsonify(db.get_reflections())

@app.route("/api/analytics", methods=["GET"])
@require_api_token
def get_analytics():
    global _analytics_cache, _analytics_cache_date
    # Parse range and week offset
    week_offset = max(0, min(520, int(request.args.get('week_offset', 0))))
    range_val = request.args.get('range', 'weekly')
    if range_val not in {'weekly', 'monthly', 'quarterly'}:
        range_val = 'weekly'
        
    from datetime import date, timedelta, datetime
    today = date.today()
    
    today_str = today.isoformat()
    
    settings = db.get_settings()
    work_keywords = settings.get("work_keywords", [])
    recharge_keywords = settings.get("recharge_keywords", [])
    
    import time
    now_time = time.time()
    write_cnt = db.analytics_write_counter
    with _analytics_cache_lock:
        if _analytics_cache_date != today:
            _analytics_cache.clear()
            _analytics_cache_date = today
            
        if len(_analytics_cache) >= 50:
            _analytics_cache.clear()
            
        cache_key = (week_offset, range_val)
        cache_val = _analytics_cache.get(cache_key)
        if (cache_val and 
            cache_val["write_counter"] == write_cnt and
            cache_val["work_keywords"] == tuple(work_keywords) and
            cache_val["recharge_keywords"] == tuple(recharge_keywords)):
            import copy
            response_data = copy.deepcopy(cache_val["data"])
            if shared_state["tracking_active"]:
                cur_mode = shared_state["current_mode"]
                elapsed = shared_state["elapsed_seconds"]
                duration = elapsed
                if duration >= 5:
                    from datetime import timedelta
                    start_time = datetime.now() - timedelta(seconds=duration)
                    ongoing_session = {
                        "mode": cur_mode,
                        "start": start_time.isoformat(),
                        "end": datetime.now().isoformat(),
                        "duration": duration,
                        "brain_dump": None,
                        "bypassed": False
                    }
                    response_data["today_sessions"].append(ongoing_session)
            return jsonify(response_data)
            
    # Monday of the current week (today.weekday() is 0 for Monday)
    current_monday = today - timedelta(days=today.weekday())
    
    # Target dates based on range
    if range_val == "monthly":
        target_monday = today - timedelta(days=30)
        target_sunday = today
        week_label = "Last 30 Days"
    elif range_val == "quarterly":
        target_monday = today - timedelta(days=90)
        target_sunday = today
        week_label = "Last 90 Days"
    else:
        target_monday = current_monday - timedelta(weeks=week_offset)
        target_sunday = target_monday + timedelta(days=6)
        
        # Format a human-readable week label
        start_label = target_monday.strftime("%b %d")
        end_label = target_sunday.strftime("%b %d, %Y")
        if week_offset == 0:
            week_label = f"Current Week ({start_label} - {end_label})"
        else:
            week_label = f"{start_label} - {end_label}"
    
    start_dt = datetime.combine(target_monday, datetime.min.time())
    end_dt = datetime.combine(target_sunday, datetime.max.time())
    
    start_date_str = target_monday.isoformat()
    end_date_str = target_sunday.isoformat()
    
    reflections = db.get_reflections(start_date=start_date_str, end_date=end_date_str)
    sessions = db.get_sessions(start_date=start_date_str, end_date=end_date_str)
    app_usage = db.get_app_usage(start_date=start_date_str, end_date=end_date_str)
    
    # Filter reflections for this week (optimized with reverse scan since reflections are chronological)
    filtered_reflections = []
    for r in reversed(reflections):
        try:
            dt = datetime.fromisoformat(r["timestamp"])
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            if dt > end_dt:
                continue
            if dt < start_dt:
                break
            filtered_reflections.append(r)
        except Exception:
            pass
    filtered_reflections.reverse()

    # Classification cache to avoid redundant regex matching across thousands of entries
    classification_cache = {}
    
    processed_app_usage = []
    # Filter app usage by target week start and end dates (optimized with reverse scan since app_usage is chronological)
    for entry in reversed(app_usage):
        entry_date = entry.get("date", "")
        if not entry_date:
            continue
        if entry_date > end_date_str or entry_date < start_date_str:
            continue
            
        process = entry.get("process", "")
        title = entry.get("title", "")
        
        # Copy and ensure all duration is accounted for in titles dict
        entry_titles = entry.get("titles")
        titles = dict(entry_titles) if isinstance(entry_titles, dict) else {}
        sum_titles_dur = sum(titles.values())
        total_dur = entry.get("duration", 0)
        if total_dur > sum_titles_dur:
            untracked_dur = total_dur - sum_titles_dur
            legacy_title = entry.get("title", "")
            if legacy_title and legacy_title != "None":
                titles[legacy_title] = titles.get(legacy_title, 0) + untracked_dur
            else:
                titles["No Title Captured"] = untracked_dur
        
        # Determine category for each title separately
        title_categories = {}
        work_dur = 0
        recharge_dur = 0
        neutral_dur = 0
        
        if titles:
            for t, dur in titles.items():
                cache_key_cls = (process, t)
                if cache_key_cls in classification_cache:
                    cat = classification_cache[cache_key_cls]
                else:
                    cat = "neutral"
                    if is_browser_process(process):
                        if matches_any_keyword(work_keywords, t):
                            cat = "work"
                        elif matches_any_keyword(recharge_keywords, t):
                            cat = "recharge"
                    else:
                        if matches_any_keyword(work_keywords, process) or matches_any_keyword(work_keywords, t):
                            cat = "work"
                        elif matches_any_keyword(recharge_keywords, process) or matches_any_keyword(recharge_keywords, t):
                            cat = "recharge"
                    classification_cache[cache_key_cls] = cat
                
                title_categories[t] = cat
                if cat == "work":
                    work_dur += dur
                elif cat == "recharge":
                    recharge_dur += dur
                else:
                    neutral_dur += dur
        else:
            # Fallback if titles is empty
            cache_key_cls = (process, title)
            if cache_key_cls in classification_cache:
                cat = classification_cache[cache_key_cls]
            else:
                cat = "neutral"
                if is_browser_process(process):
                    if matches_any_keyword(work_keywords, title):
                        cat = "work"
                    elif matches_any_keyword(recharge_keywords, title):
                        cat = "recharge"
                else:
                    if matches_any_keyword(work_keywords, process) or matches_any_keyword(work_keywords, title):
                        cat = "work"
                    elif matches_any_keyword(recharge_keywords, process) or matches_any_keyword(recharge_keywords, title):
                        cat = "recharge"
                classification_cache[cache_key_cls] = cat
            title_categories[title] = cat
            dur = entry.get("duration", 0)
            if cat == "work":
                work_dur += dur
            elif cat == "recharge":
                recharge_dur += dur
            else:
                neutral_dur += dur

        # Predominant category is the one with the maximum duration
        if work_dur >= recharge_dur and work_dur >= neutral_dur:
            predominant_category = "work"
        elif recharge_dur >= work_dur and recharge_dur >= neutral_dur:
            predominant_category = "recharge"
        else:
            predominant_category = "neutral"
            
        processed_app_usage.append({
            "date": entry.get("date"),
            "process": process,
            "title": title,
            "titles": titles,
            "duration": entry.get("duration", 0),
            "category": predominant_category,
            "work_duration": work_dur,
            "recharge_duration": recharge_dur,
            "neutral_duration": neutral_dur,
            "title_categories": title_categories
        })
    
    # Calculate energy vs friction mapping for target week
    energy_levels = [r["energy_level"] for r in filtered_reflections]
    friction_levels = [r["friction_level"] for r in filtered_reflections]
    
    # Compute average energy and friction per weekday based on target week
    weekday_data = {i: {"energy": [], "friction": [], "count": 0} for i in range(7)}
    for r in filtered_reflections:
        try:
            dt = datetime.fromisoformat(r["timestamp"])
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            w = dt.weekday() # 0 = Monday, 6 = Sunday
            weekday_data[w]["energy"].append(r["energy_level"])
            weekday_data[w]["friction"].append(r["friction_level"])
            weekday_data[w]["count"] += 1
        except Exception:
            pass
            
    weekday_summary = []
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for w in range(7):
        energy_avg = sum(weekday_data[w]["energy"]) / len(weekday_data[w]["energy"]) if weekday_data[w]["energy"] else 0
        friction_avg = sum(weekday_data[w]["friction"]) / len(weekday_data[w]["friction"]) if weekday_data[w]["friction"] else 0
        weekday_summary.append({
            "day": days[w],
            "avg_energy": round(energy_avg, 2),
            "avg_friction": round(friction_avg, 2),
            "count": weekday_data[w]["count"]
        })

    # Find correlations and recommendations
    recommendations = []
    high_friction_count = sum(1 for f in friction_levels if f >= 4)
    low_energy_count = sum(1 for e in energy_levels if e <= 2)
    
    if high_friction_count > 0:
        recommendations.append(
            "We detected high task friction in multiple sessions. Consider breaking down your "
            "work blocks into shorter 30-minute intervals and adding a mandatory 5-minute Recharge block."
        )
    if low_energy_count > 2:
        recommendations.append(
            "Your energy levels have dipped frequently. Make sure you do not work during Rest Mode "
            "and take full physical breaks away from the screen."
        )
    if not recommendations:
        recommendations.append(
            "Your routine looks balanced! Keep logging your daily states to refine your battery predictions."
        )

    # Filter sessions for this week (optimized with reverse scan since sessions are chronological)
    filtered_sessions = []
    for s in reversed(sessions):
        try:
            s_start = s.get("start", "")
            if not s_start:
                continue
            if s_start > end_date_str + "T23:59:59":
                continue
            if s_start < start_date_str:
                break
            filtered_sessions.append(s)
        except Exception:
            pass
    filtered_sessions.reverse()

    # Compute high-quality structured premium insights (scoped to the selected week)
    insights = []
    
    total_work = 0
    total_rest_recharge = 0
    bypassed_count = 0
    for s in filtered_sessions:
        mode = s.get("mode")
        duration = s.get("duration", 0)
        if mode == "work":
            total_work += duration
        elif mode in ["recharge", "rest"]:
            total_rest_recharge += duration
        if s.get("bypassed", False):
            bypassed_count += 1

    # Insight 1: Focus/Recharge Ratio
    if total_work > 0:
        ratio = total_work / (total_rest_recharge + 1)
        if ratio > 4.5:
            insights.append({
                "id": "focus_ratio",
                "title": "Burnout Susceptibility",
                "type": "danger",
                "icon": "🚨",
                "metric": f"{ratio:.1f}:1 Ratio",
                "description": "Your focused work time is extremely high compared to your rest/recovery periods. Working in prolonged blocks without breaks leads to mental fatigue, cognitive bottlenecks, and slower problem-solving.",
                "actionable_tip": "Shorten your work blocks to 25-30 minutes and force a 5-minute physical break away from the screen."
            })
        elif 2.0 <= ratio <= 4.5:
            insights.append({
                "id": "focus_ratio",
                "title": "Focus Balance",
                "type": "success",
                "icon": "⚖️",
                "metric": f"{ratio:.1f}:1 Ratio",
                "description": "Excellent! Your focus-to-rest ratio is in the optimal performance zone. This sustainable pace prevents mental burnout while maintaining strong daily progress.",
                "actionable_tip": "Maintain this cadence. Tag your reflections to lock in what keeps you in this balanced flow."
            })
        else:
            insights.append({
                "id": "focus_ratio",
                "title": "Cognitive Recovery",
                "type": "info",
                "icon": "🔋",
                "metric": f"{ratio:.1f}:1 Ratio",
                "description": "You are spending a significant portion of your time resting and recharging. This is excellent for deep fatigue recovery, but ensure your focus blocks are highly focused.",
                "actionable_tip": "When you start a focus block, hide distractions and let MIND-FLOW clean your workspace automatically."
            })

    # Insight 2: Bypassed Breaks
    if bypassed_count > 0:
        insights.append({
            "id": "bypassed_breaks",
            "title": "Break Compliance",
            "type": "warning",
            "icon": "⚠️",
            "metric": f"{bypassed_count} Skipped",
            "description": f"You have bypassed {bypassed_count} visual shield lockout breaks. Skipping eye strain breaks diminishes focus quality and increases neural fatigue over time.",
            "actionable_tip": "When the lockout activates, look at an object 20 feet away for 20 seconds. It is a quick recharge that preserves your long-term focus."
        })
    elif total_work > 0:
        insights.append({
            "id": "bypassed_breaks",
            "title": "Break Discipline",
            "type": "success",
            "icon": "🛡️",
            "metric": "100% Guarded",
            "description": "Perfect score! You have respected every visual shield lockout break. Your focus blocks are safely buffered, preventing eye strain and cognitive decline.",
            "actionable_tip": "Keep it up. Regular micro-breaks keep your brain primed for complex debugging tasks."
        })

    # Insight 3: High Friction Hotspots (scoped to selected week)
    high_friction_reflections = [r for r in filtered_reflections if r["friction_level"] >= 4]
    if high_friction_reflections:
        recent_refl = high_friction_reflections[-1]
        insights.append({
            "id": "friction_hotspot",
            "title": "Friction Hotspot",
            "type": "warning",
            "icon": "🚧",
            "metric": f"{len(high_friction_reflections)} Alerts",
            "description": f"High task friction detected in recent focus sessions. Your latest obstacle was: '{recent_refl.get('summary', '')}'. High friction points to structural roadblocks or mental fatigue.",
            "actionable_tip": "Divide your current complex task into small sub-tasks. Check in with tags like 'Coding Win' to boost motivation."
        })
    elif filtered_reflections:
        insights.append({
            "id": "friction_hotspot",
            "title": "Friction Status",
            "type": "success",
            "icon": "🌊",
            "metric": "Low Friction",
            "description": "Your tasks are progressing smoothly with minimal mental roadblocks. You are in a clear cognitive state.",
            "actionable_tip": "This is the best time to tackle your most complex architectural designs or key features."
        })

    # Insight 4: Autopilot Status
    autopilot_enabled = settings.get("adaptive_timers_enabled", True)
    adaptive = db.get_adaptive_times()
    work_mins = adaptive.get("work_minutes", 25)
    if autopilot_enabled:
        insights.append({
            "id": "autopilot_status",
            "title": "Autopilot Sprints",
            "type": "info",
            "icon": "⚙️",
            "metric": f"{work_mins}m Limit",
            "description": f"Cognitive Autopilot is active and dynamically calibrating your focus limits. It has tuned your focus sprint to {work_mins} minutes based on recent check-in ratings.",
            "actionable_tip": "Let Autopilot handle the timing. It automatically shortens blocks when you are tired and expands them during peak flow."
        })
    else:
        insights.append({
            "id": "autopilot_status",
            "title": "Autopilot Status",
            "type": "info",
            "icon": "💤",
            "metric": "Static Timers",
            "description": "Autopilot is off. MIND-FLOW is using static timers. Your blocks will not adjust to your actual fatigue levels.",
            "actionable_tip": "Enable Autopilot in Preferences to let the companion adapt dynamically to your daily cognitive capacity."
        })

    # Insight 5: Circadian Peak Energy (optimized to scan latest 100 reflections to avoid all-time database overhead)
    time_groups = {"morning": [], "afternoon": [], "evening": [], "night": []}
    for r in reflections[-100:]:
        try:
            dt = datetime.fromisoformat(r["timestamp"])
            h = dt.hour
            if 6 <= h < 12:
                time_groups["morning"].append(r["energy_level"])
            elif 12 <= h < 18:
                time_groups["afternoon"].append(r["energy_level"])
            elif 18 <= h < 24:
                time_groups["evening"].append(r["energy_level"])
            else:
                time_groups["night"].append(r["energy_level"])
        except Exception:
            pass

    peak_period = None
    max_avg = 0
    for k, v in time_groups.items():
        if v:
            avg = sum(v) / len(v)
            if avg > max_avg:
                max_avg = avg
                peak_period = k

    if peak_period:
        periods = {"morning": "Morning", "afternoon": "Afternoon", "evening": "Evening", "night": "Late Night"}
        insights.append({
            "id": "peak_energy",
            "title": "Peak Energy Window",
            "type": "success",
            "icon": "📈",
            "metric": f"Avg {max_avg:.1f}/5",
            "description": f"Your self-reported energy levels are highest during the {periods[peak_period]}. Your brain is in its prime state during this window.",
            "actionable_tip": "Schedule your most demanding deep work tasks (like refactoring or complex architecture) during this peak period."
        })
        
    base_today_sessions = []
    for s in reversed(sessions):
        if s["start"].startswith(today_str):
            base_today_sessions.append(s)
        else:
            try:
                if datetime.fromisoformat(s["start"]).date() < today:
                    break
            except Exception:
                pass
    base_today_sessions.reverse()

    mood_counts = {m: 0 for m in ["Calm", "Focused", "Anxious", "Overwhelmed", "Frustrated", "Exhausted", "Neutral"]}
    for r in filtered_reflections:
        mood = r.get("mood")
        if mood in mood_counts:
            mood_counts[mood] += 1

    # Count context switches in range
    switches_in_range = 0
    try:
        for sw in db.get_context_switches():
            sw_date = sw["timestamp"][:10]
            if start_date_str <= sw_date <= end_date_str:
                switches_in_range += 1
    except Exception:
        pass

    # Sum flow minutes in range
    flow_minutes = 0.0
    try:
        flow_minutes = round(sum(s.get("flow_duration", 0.0) or 0.0 for s in filtered_sessions) / 60.0, 1)
    except Exception:
        pass

    base_data = {
        "reflections": filtered_reflections[-15:], # Send last 15 filtered reflections for recent list
        "weekday_summary": weekday_summary,
        "recommendations": recommendations,
        "insights": insights,
        "total_reflections": len(reflections),
        "total_sessions": len(sessions),
        "today_sessions": base_today_sessions,
        "app_usage": processed_app_usage,
        "week_label": week_label,
        "mood_counts": mood_counts,
        "total_context_switches": switches_in_range,
        "context_switches_hourly": db.get_context_switches_hourly(),
        "focus_score_history": db.get_focus_score_history(30 if range_val == 'monthly' else (90 if range_val == 'quarterly' else 7)),
        "flow_minutes": flow_minutes,
        "calming_narrative": generate_calming_narrative()
    }
    with _analytics_cache_lock:
        _analytics_cache[(week_offset, range_val)] = {
            "time": now_time,
            "data": base_data,
            "write_counter": write_cnt,
            "work_keywords": tuple(work_keywords),
            "recharge_keywords": tuple(recharge_keywords)
        }
    import copy
    response_data = copy.deepcopy(base_data)

# Add ongoing session in real-time to the timeline
    if shared_state["tracking_active"]:
        cur_mode = shared_state["current_mode"]
        elapsed = shared_state["elapsed_seconds"]
        duration = elapsed
        if duration >= 5:
            from datetime import timedelta
            start_time = datetime.now() - timedelta(seconds=duration)
            ongoing_session = {
                "mode": cur_mode,
                "start": start_time.isoformat(),
                "end": datetime.now().isoformat(),
                "duration": duration,
                "brain_dump": None,
                "bypassed": False
            }
            response_data["today_sessions"].append(ongoing_session)

    return jsonify(response_data)


@app.route("/api/app_rules", methods=["GET", "POST", "DELETE"])
@require_local_origin
@require_api_token
def manage_app_rules():
    if request.method == "GET":
        settings = db.get_settings()
        return jsonify({
            "status": "success",
            "rules": db.get_app_rules(),
            "work_keywords": settings.get("work_keywords", []),
            "recharge_keywords": settings.get("recharge_keywords", []),
            "neutral_keywords": settings.get("neutral_keywords", [])
        })
    elif request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        app_name = data.get("app_name", "").strip()
        category = data.get("category", "work").strip().lower()
        if not app_name:
            return jsonify({"status": "error", "message": "app_name is required"}), 400
        db.recategorize_app(app_name, category)
        return jsonify({"status": "success", "rules": db.get_app_rules()})
    elif request.method == "DELETE":
        data = request.get_json(force=True, silent=True) or {}
        app_name = data.get("app_name") or request.args.get("app_name")
        if not app_name:
            return jsonify({"status": "error", "message": "app_name is required"}), 400
        db.delete_app_rule(app_name)
        return jsonify({"status": "success", "rules": db.get_app_rules()})

@app.route("/api/app_rules/recategorize", methods=["POST"])
@require_local_origin
@require_api_token
def recategorize_app_route():
    data = request.get_json(force=True, silent=True) or {}
    app_name = data.get("app_name", "").strip()
    category = data.get("category", "neutral").strip().lower()
    if not app_name:
        return jsonify({"status": "error", "message": "app_name is required"}), 400
    db.recategorize_app(app_name, category)
    return jsonify({"status": "success", "rules": db.get_app_rules()})

_running_apps_cache = None
_running_apps_cache_time = 0.0
_running_apps_cache_lock = threading.Lock()

@app.route("/api/app_rules/running", methods=["GET"])
@app.route("/api/active_processes", methods=["GET"])
@require_api_token
def get_running_apps():
    global _running_apps_cache, _running_apps_cache_time
    now = time.time()
    with _running_apps_cache_lock:
        if _running_apps_cache is not None and (now - _running_apps_cache_time) < 5.0:
            return jsonify({"running_apps": _running_apps_cache})

    running_apps = []
    seen = set()
    if psutil is not None:
        try:
            for p in psutil.process_iter(['name']):
                try:
                    name = p.info.get('name')
                    if name and name.lower() not in seen:
                        name_lower = name.lower()
                        if not any(skip in name_lower for skip in ['svchost', 'system', 'idle', 'conhost', 'runtimebroker', 'searchhost', 'taskhostw', 'csrss', 'smss', 'lsass', 'services', 'wininit', 'dllhost', 'wmiprvse']):
                            seen.add(name_lower)
                            disp = name.replace(".exe", "").replace(".EXE", "")
                            disp = disp.capitalize() if len(disp) > 0 else disp
                            running_apps.append({
                                "process": name,
                                "display_name": disp
                            })
                except Exception:
                    pass
        except Exception as e:
            print(f"Error enumerating running processes: {e}")
    running_apps.sort(key=lambda x: x["display_name"].lower())
    
    with _running_apps_cache_lock:
        _running_apps_cache = running_apps
        _running_apps_cache_time = time.time()

    return jsonify({"running_apps": running_apps})

@app.route("/api/app_rules/recent", methods=["GET"])
@require_api_token
def get_recent_apps_route():
    return jsonify({"recent_apps": db.get_recent_apps()})


@app.route("/api/workspace/status", methods=["GET"])
@require_api_token
def get_workspace_status():
    from backend.workspace_manager import WorkspaceManager
    from backend.database import get_default_data_dir
    try:
        workspace_mgr = WorkspaceManager(get_default_data_dir())
        cloud_sync = workspace_mgr.detect_cloud_sync()
        
        # List files in profiles
        work_files = []
        recharge_files = []
        
        work_dir = os.path.join(workspace_mgr.profiles_dir, "Work")
        if os.path.exists(work_dir):
            work_files = [f for f in os.listdir(work_dir) if f.lower() not in ["work_readme.txt", "work_readme.txt.bak"]]
            
        recharge_dir = os.path.join(workspace_mgr.profiles_dir, "Recharge")
        if os.path.exists(recharge_dir):
            recharge_files = [f for f in os.listdir(recharge_dir) if f.lower() not in ["recharge_readme.txt", "recharge_readme.txt.bak"]]
            
        return jsonify({
            "cloud_sync": cloud_sync,
            "current_mode": shared_state["current_mode"],
            "work_files": work_files,
            "recharge_files": recharge_files
        })
    except Exception as e:
        logger.exception("Error in get_workspace_status: %s", e)
        return jsonify({"status": "error", "message": "Failed to retrieve workspace status"}), 500

@app.route("/api/workspace/restore", methods=["POST"])
@require_local_origin
@require_api_token
def emergency_restore_workspace():
    def _restore_worker():
        try:
            from backend.workspace_manager import WorkspaceManager
            from backend.database import get_default_data_dir
            workspace_mgr = WorkspaceManager(get_default_data_dir())
            restored = workspace_mgr.emergency_restore_all()
            print(f"Workspace restore completed: {restored} files restored.")
        except Exception as e:
            print(f"Workspace restore error: {e}")
    
    _workspace_executor.submit(_restore_worker)
    return jsonify({"status": "success", "message": "Workspace restore initiated in background."})

@app.route("/api/shutdown", methods=["POST"])
@require_local_origin
@require_api_token
def shutdown_app():
    cur_mode = shared_state["current_mode"]
    
    print(f"Shutdown requested via API. Transitioning {cur_mode} -> neutral...")
    
    # Flush remaining app usage
    last_proc = shared_state.get("last_app_process")
    last_title = shared_state.get("last_app_title")
    accum_sec = shared_state.get("app_accumulated_seconds", 0)
    if last_proc and accum_sec > 0:
        try:
            db.log_app_usage(last_proc, last_title, accum_sec)
        except Exception as e:
            print(f"Error logging app usage on shutdown: {e}")

    mode_start_time = shared_state.get("mode_start_time")
    if cur_mode in {"work", "recharge", "rest"} and hasattr(mode_start_time, "isoformat"):
        try:
            db.log_session(cur_mode, mode_start_time, datetime.now())
        except Exception as e:
            print(f"Error logging session on shutdown: {e}")
    
    # Graceful shutdown: flush database and exit cleanly
    try:
        db.save()
    except Exception as e:
        print(f"Error saving database on shutdown: {e}")
        
    def terminate():
        import time
        time.sleep(0.5)
        # Sweep back all workspace files on shutdown
        try:
            from backend.workspace_manager import WorkspaceManager
            from backend.database import get_default_data_dir
            workspace_mgr = WorkspaceManager(get_default_data_dir())
            workspace_mgr.sweep_back_all()
        except Exception as e:
            print(f"Error sweeping workspace on API shutdown: {e}")
        db.save(sync=True)  # Ensure final data flush before exit
        import os
        os._exit(0)
        
    import threading
    threading.Thread(target=terminate, daemon=True).start()
    return jsonify({"status": "shutdown_initiated"})


def generate_calming_narrative():
    from datetime import date, datetime, timedelta
    today = date.today()
    
    # Gather data for the last 7 days
    sleep_days = []
    steps_days = []
    energy_days = []
    friction_days = []
    bypassed_breaks = 0
    
    # Load settings
    settings = db.get_settings()
    sleep_target = settings.get("daily_sleep_target", 8.0)
    step_target = settings.get("daily_step_target", 10000)
    
    # Scan sleep, steps, reflections, and sessions for the last 7 days only
    seven_days_ago = today - timedelta(days=6)
    seven_days_ago_str = seven_days_ago.isoformat()
    
    if True:
        sleep_list = db.get_sleep_list(start_date=seven_days_ago_str)
        steps_list = db.get_steps_list(start_date=seven_days_ago_str)
        reflections = db.get_reflections(start_date=seven_days_ago_str)
        sessions = db.get_sessions(start_date=seven_days_ago_str)
        
        # Get last 7 days strings
        last_7_days = [(today - timedelta(days=i)).isoformat() for i in range(7)]
        
        for d in last_7_days:
            # Sleep hours
            for s in sleep_list:
                if s.get("date") == d:
                    sleep_days.append(s.get("hours", 0.0))
                    break
            # Steps
            for st in steps_list:
                if st.get("date") == d:
                    steps_days.append(st.get("count", 0))
                    break
                    
            # Reflections on that day
            day_energy = []
            day_friction = []
            for r in reflections:
                try:
                    r_dt = datetime.fromisoformat(r["timestamp"])
                    # Remove timezone if any
                    if r_dt.tzinfo is not None:
                        r_dt = r_dt.replace(tzinfo=None)
                    if r_dt.date().isoformat() == d:
                        day_energy.append(r.get("energy_level", 3))
                        day_friction.append(r.get("friction_level", 3))
                except Exception:
                    pass
            if day_energy:
                energy_days.append(sum(day_energy) / len(day_energy))
            if day_friction:
                friction_days.append(sum(day_friction) / len(day_friction))
                
        # Count bypasses in the last 7 days
        for s in sessions:
            try:
                s_dt = datetime.fromisoformat(s["start"])
                if s_dt.tzinfo is not None:
                    s_dt = s_dt.replace(tzinfo=None)
                if (today - s_dt.date()).days < 7:
                    if s.get("bypassed", False):
                        bypassed_breaks += 1
            except Exception:
                pass

    # Compute averages
    avg_sleep = sum(sleep_days) / len(sleep_days) if sleep_days else 0.0
    avg_steps = sum(steps_days) / len(steps_days) if steps_days else 0
    avg_energy = sum(energy_days) / len(energy_days) if energy_days else 3.0
    avg_friction = sum(friction_days) / len(friction_days) if friction_days else 3.0

    # Build correlation points
    narrative_parts = []
    
    # 1. Sleep correlation
    if avg_sleep > 0:
        if avg_sleep >= sleep_target:
            narrative_parts.append(f"Your sleep averaged a restful {avg_sleep:.1f} hours, meeting your daily target. Adequate sleep keeps your mind shielded against quick friction.")
        else:
            narrative_parts.append(f"Your sleep averaged {avg_sleep:.1f} hours, which is slightly below your {sleep_target}h target. Tending to sleep is the foundation of cognitive rest.")
    else:
        narrative_parts.append("Consider logging your sleep hours on the dashboard to build calming bedtime insights.")
        
    # 2. Steps correlation
    if avg_steps > 0:
        if avg_steps >= step_target:
            narrative_parts.append(f"With an average of {avg_steps:,.0f} steps daily, you achieved your movement goal. Mindful movement helps balance your energy.")
        else:
            narrative_parts.append(f"You walked an average of {avg_steps:,.0f} steps. Taking even a brief, gentle walk can clear build-up stress.")
            
    # 3. Energy / Stress correlation
    if avg_friction > 3.0:
        narrative_parts.append(f"We noticed higher friction levels ({avg_friction:.1f}/5) this week. When friction rises, your focus energy benefits from shorter, gentle sprints.")
    else:
        narrative_parts.append(f"Your focus friction remained low and steady ({avg_friction:.1f}/5), keeping your cognitive shield calm.")
        
    # 4. Break bypasses
    if bypassed_breaks > 0:
        narrative_parts.append(f"You bypassed {bypassed_breaks} rest breaks this week. Remember: taking a micro-break is not a delay, it is a restoration.")
    else:
        narrative_parts.append("You completed all your scheduled rest breaks without bypasses. A perfect rhythm of work and rest.")

    return " ".join(narrative_parts)

@app.route("/api/vitality", methods=["GET", "POST"])
@require_local_origin
@require_api_token
def manage_vitality():
    from datetime import date
    date_str = None
    if request.is_json:
        data = request.get_json(force=True, silent=True) or {}
        date_str = data.get("date")
    if not date_str:
        date_str = request.args.get("date")
    if not date_str:
        date_str = date.today().isoformat()
        
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid payload"}), 400
        
        if "steps" in data:
            try:
                steps = int(data["steps"])
                if steps >= 0 and steps <= 200000:
                    db.log_steps(steps, date_str)
            except (ValueError, TypeError):
                pass
                
        if "sleep_hours" in data or "sleep_quality" in data:
            try:
                existing = db.get_sleep(date_str)
                hours = float(data.get("sleep_hours", existing.get("hours", 0.0)))
                quality = int(data.get("sleep_quality", existing.get("quality", 3)))
                if 0 <= hours <= 24 and 1 <= quality <= 5:
                    db.log_sleep(hours, quality, date_str)
            except (ValueError, TypeError):
                pass
                
        if "hydration_cups" in data:
            try:
                cups = int(data["hydration_cups"])
                if 0 <= cups <= 50:
                    db.increment_hydration(cups)
            except (ValueError, TypeError):
                pass
            
    settings = db.get_settings()
    hyd_data = db.get_hydration()
    steps_count = db.get_steps(date_str)
    sleep_data = db.get_sleep(date_str)
    
    return jsonify({
        "date": date_str,
        "steps": steps_count,
        "sleep_hours": sleep_data["hours"],
        "sleep_quality": sleep_data["quality"],
        "hydration_cups": hyd_data.get("cups", 0),
        "step_target": settings.get("daily_step_target", 10000),
        "sleep_target": settings.get("daily_sleep_target", 8.0),
        "hydration_target": settings.get("hydration_target", 8)
    })

@app.route("/api/tasks", methods=["GET", "POST", "PUT", "DELETE"])
@require_local_origin
@require_api_token
def manage_tasks():
    if request.method == "GET":
        return jsonify(db.get_tasks())
    elif request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"error": "Task text is required"}), 400
        new_task = db.add_task(text)
        return jsonify({"status": "success", "task": new_task})
    elif request.method == "PUT":
        data = request.get_json(force=True, silent=True) or {}
        task_id = data.get("id")
        try:
            task_id = int(task_id) if task_id is not None else None
            completed = int(data.get("completed", 0))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid ID or completed type"}), 400
        if task_id is None:
            return jsonify({"error": "Task ID is required"}), 400
        updated = db.update_task(task_id, completed)
        if not updated:
            return jsonify({"error": "Task not found"}), 404
        return jsonify({"status": "success"})
    elif request.method == "DELETE":
        task_id = request.args.get("id")
        if task_id is None:
            data = request.get_json(force=True, silent=True) or {}
            task_id = data.get("id")
        if task_id is None:
            return jsonify({"error": "Task ID is required"}), 400
        try:
            task_id = int(task_id)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid task ID"}), 400
        deleted = db.delete_task(task_id)
        if not deleted:
            return jsonify({"error": "Task not found"}), 404
        return jsonify({"status": "success"})

@app.route("/api/gratitude", methods=["GET", "POST"])
@require_local_origin
@require_api_token
def manage_gratitude():
    from datetime import date
    date_str = request.args.get("date")
    if not date_str:
        date_str = date.today().isoformat()
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid payload"}), 400
        entry_1 = str(data.get("entry_1", "")).strip()[:1000]
        entry_2 = str(data.get("entry_2", "")).strip()[:1000]
        entry_3 = str(data.get("entry_3", "")).strip()[:1000]
        db.add_gratitude(date_str, entry_1, entry_2, entry_3)
        return jsonify({"status": "success"})
    else:
        res = db.get_gratitude(date_str)
        if not res:
            res = {"date": date_str, "entry_1": "", "entry_2": "", "entry_3": ""}
        return jsonify(res)

@app.route("/api/achievements", methods=["GET"])
@require_local_origin
@require_api_token
def get_achievements_list():
    return jsonify(db.get_achievements())

@app.route("/api/analytics/digest", methods=["GET"])
@require_local_origin
@require_api_token
def get_digest_report():
    from datetime import datetime, date, timedelta
    digest_range = request.args.get("range", "weekly")
    
    today = date.today()
    if digest_range == "daily":
        days_count = 1
        title = "Daily Cognitive Digest"
    elif digest_range == "monthly":
        days_count = 30
        title = "Monthly Cognitive Digest"
    else:
        days_count = 7
        title = "Weekly Cognitive Digest"
        
    start_date = today - timedelta(days=days_count-1)
    
    start_str = start_date.isoformat()
    end_str = today.isoformat()
    
    sessions = db.get_sessions(start_date=start_str, end_date=end_str)
    reflections = db.get_reflections(start_date=start_str, end_date=end_str)
    
    total_work = 0
    total_rest = 0
    total_recharge = 0
    bypasses = 0
    accomplishments = []
    
    start_str = start_date.isoformat()
    for s in sessions:
        if s["start"] >= start_str:
            dur = s["duration"]
            if s["mode"] == "work":
                total_work += dur
                if s.get("brain_dump") and "[Bypassed" not in s["brain_dump"] and "[Break Completed" not in s["brain_dump"]:
                    accomplishments.append(s["brain_dump"])
            elif s["mode"] == "rest":
                total_rest += dur
            elif s["mode"] == "recharge":
                total_recharge += dur
            if s.get("bypassed"):
                bypasses += 1
                
    energy_levels = []
    friction_levels = []
    for r in reflections:
        if r["timestamp"] >= start_str:
            energy_levels.append(r["energy_level"])
            friction_levels.append(r["friction_level"])
            
    avg_energy = sum(energy_levels) / len(energy_levels) if energy_levels else 3.0
    avg_friction = sum(friction_levels) / len(friction_levels) if friction_levels else 1.0
    
    recommendations = []
    if bypasses > 2:
        recommendations.append("High break skipping detected. Bypassing lockouts impacts sustained focus. Plan to step away next cycle.")
    if avg_friction > 3.0:
        recommendations.append("Task friction is high. We recommend breaking down complex goals into checklist tasks under 30 minutes.")
    if not recommendations:
        recommendations.append("Balanced cadence. You are maintaining excellent pacing between sprints and recovery blocks.")
        
    unique_acc = list(set(accomplishments))[:5]
    
    return jsonify({
        "title": title,
        "range": digest_range,
        "period": f"{start_date.strftime('%B %d')} - {today.strftime('%B %d, %Y')}",
        "total_focus_hours": round(total_work / 3600.0, 1),
        "total_recovery_hours": round((total_rest + total_recharge) / 3600.0, 1),
        "bypasses_count": bypasses,
        "avg_energy": round(avg_energy, 1),
        "avg_friction": round(avg_friction, 1),
        "accomplishments": unique_acc,
        "recommendations": recommendations,
        "unlocked_achievements_count": len(db.get_achievements())
    })

def is_safe_url(url):
    import socket
    import ipaddress
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        if hostname.lower() in {'localhost', '127.0.0.1', '[::1]'}:
            return False
        addr_info = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return False
        return True
    except Exception:
        return False

_calendar_sync_lock = threading.Lock()

@app.route("/api/calendar/sync", methods=["POST"])
@require_local_origin
@require_api_token
def sync_calendar():
    import re
    from datetime import datetime, date
    data = request.get_json(force=True, silent=True) or {}
    ical_url = data.get("ical_url", "").strip()
    
    # Return existing events from DB immediately
    existing_events = []
    if True:
        with db.connection() as conn:
            db_events = conn.execute("SELECT title, start_time, end_time FROM calendar_events").fetchall()
    if db_events:
        existing_events = [{"title": row["title"], "start_time": row["start_time"], "end_time": row["end_time"]} for row in db_events]
    else:
        today_str = date.today().isoformat()
        existing_events = [
            {"title": "🎯 Daily Team Standup", "start_time": f"{today_str}T10:00:00", "end_time": f"{today_str}T10:30:00"},
            {"title": "🏛️ Core System Architecture Review", "start_time": f"{today_str}T14:00:00", "end_time": f"{today_str}T15:00:00"},
            {"title": "☕ 1-on-1 Pacing & Sync", "start_time": f"{today_str}T16:30:00", "end_time": f"{today_str}T17:00:00"}
        ]

    if ical_url and is_safe_url(ical_url):
        if _calendar_sync_lock.locked():
            return jsonify({"status": "success", "message": "Sync is already in progress.", "events": existing_events})

        def _sync_worker(url):
            if not _calendar_sync_lock.acquire(blocking=False):
                print("[Warning] Calendar sync already in progress, skipping duplicate sync thread.")
                return
            try:
                import urllib.request
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    MAX_ICAL_BYTES = 2 * 1024 * 1024
                    ical_data = response.read(MAX_ICAL_BYTES).decode('utf-8', errors='ignore')
                    
                events = []
                matches = re.findall(r"BEGIN:VEVENT.*?END:VEVENT", ical_data, re.DOTALL)
                for m in matches[:10]:
                    summary_m = re.search(r"SUMMARY:(.*?)\r?\n", m)
                    dtstart_m = re.search(r"DTSTART;?[^:]*:(.*?)\r?\n", m)
                    dtend_m = re.search(r"DTEND;?[^:]*:(.*?)\r?\n", m)
                    if summary_m and dtstart_m:
                        title = summary_m.group(1).strip()
                        raw_start = dtstart_m.group(1).strip()
                        try:
                            clean_start = re.sub(r'[^0-9T]', '', raw_start)
                            if 'T' in clean_start:
                                dt_start = datetime.strptime(clean_start[:15], "%Y%m%dT%H%M%S")
                            else:
                                dt_start = datetime.strptime(clean_start[:8], "%Y%m%d")
                            start_time = dt_start.isoformat()
                            
                            if dtend_m:
                                clean_end = re.sub(r'[^0-9T]', '', dtend_m.group(1).strip())
                                if 'T' in clean_end:
                                    dt_end = datetime.strptime(clean_end[:15], "%Y%m%dT%H%M%S")
                                else:
                                    dt_end = datetime.strptime(clean_end[:8], "%Y%m%d")
                                end_time = dt_end.isoformat()
                            else:
                                end_time = start_time
                                
                            events.append({"title": title, "start_time": start_time, "end_time": end_time})
                        except Exception as parse_e:
                            print(f"Error parsing ical event date: {parse_e}")
                
                db.save_calendar_events(events)
            except Exception as sync_e:
                print(f"Calendar sync download error: {sync_e}")
            finally:
                _calendar_sync_lock.release()
        
        sync_thread = threading.Thread(target=_sync_worker, args=(ical_url,), daemon=True)
        sync_thread.start()

    return jsonify({"status": "success", "events": existing_events})

@app.route("/api/focus/log", methods=["POST"])
@require_local_origin
@require_api_token
def log_focus_session_endpoint():
    data = request.get_json(force=True, silent=True) or {}
    duration = max(1, min(720, int(data.get("duration_minutes", 25))))
    task_label = str(data.get("task_label", "")).strip()[:200]
    completed = 1 if data.get("completed", 1) else 0
    stamina_start = max(0.0, min(100.0, float(data.get("stamina_start", 100.0))))
    stamina_end = max(0.0, min(100.0, float(data.get("stamina_end", 100.0))))

    db.log_focus_session(
        duration_minutes=duration,
        task_label=task_label,
        completed=completed,
        stamina_start=stamina_start,
        stamina_end=stamina_end
    )
    return jsonify({"status": "success", "message": "Focus session logged successfully."})

@app.route("/api/focus/stats", methods=["GET"])
@require_api_token
def get_focus_stats_endpoint():
    days = request.args.get("days", 7, type=int) or 7
    stats = db.get_focus_session_stats(days=days)
    return jsonify({"status": "success", "stats": stats})

@app.route("/api/context-switches", methods=["GET"])
@require_api_token
def get_context_switches_endpoint():
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    limit_arg = request.args.get("limit", 200, type=int)
    limit = min(limit_arg or 200, 500)
    switches = db.get_context_switches(date_str=date_str, limit=limit)
    return jsonify({"status": "success", "date": date_str, "switches": switches})

@app.route("/api/sessions/history", methods=["GET"])
@require_api_token
def get_session_history_endpoint():
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    sessions = db.get_sessions(start_date=date_str, end_date=date_str)
    return jsonify({"status": "success", "date": date_str, "sessions": sessions})


def run_server(port=5000):
    # Run flask app on localhost and port 5000
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    run_server()
