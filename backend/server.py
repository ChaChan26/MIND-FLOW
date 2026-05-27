import os
import sys
from functools import wraps
from datetime import datetime, date
from urllib.parse import urlparse
from flask import Flask, jsonify, request, send_from_directory

def require_local_origin(f):
    """CSRF protection: reject POST requests from foreign Origins."""
    @wraps(f)
    def decorated(*args, **kwargs):
        origin = request.headers.get('Origin', '')
        referer = request.headers.get('Referer', '')
        allowed_hosts = {'127.0.0.1', 'localhost'}
        
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
                    return jsonify({"error": "Forbidden: invalid referer"}), 403
            except Exception:
                return jsonify({"error": "Forbidden: invalid referer"}), 403
                
        if not origin and not referer:
            # If both are missing, ensure request is strictly local
            remote = request.remote_addr
            if remote not in {'127.0.0.1', '::1', None, ''}:
                return jsonify({"error": "Forbidden: missing origin/referer verification"}), 403

        return f(*args, **kwargs)
    return decorated

# Adjust path to import from parent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database import MindFlowDB, matches_keyword

def get_resource_path(relative_path):
    """ Get absolute path to resource, prioritizing local disk paths before PyInstaller bundled ones """
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.abspath(os.path.dirname(sys.executable))
        parent_dir = os.path.abspath(os.path.join(exe_dir, ".."))
        
        # Check parent folder, executable folder, or hardcoded C:\MIND folder
        for base in [parent_dir, exe_dir, r"C:\MIND"]:
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

@app.before_request
def validate_host():
    """Verify that the Host header is strictly local to prevent DNS Rebinding."""
    host = request.host
    if not host:
        # Fallback to remote_addr if Host is missing (e.g. some internal tests)
        remote = request.remote_addr
        if remote not in {'127.0.0.1', '::1', None, ''}:
            return jsonify({"error": "Forbidden: Missing Host header"}), 400
        return
    
    hostname = host.split(':')[0].lower()
    if hostname not in {'localhost', '127.0.0.1', '[::1]'}:
        return jsonify({"error": "Forbidden: Invalid Host header"}), 403

# In-memory shared state between Flask thread and Background Watcher thread
shared_state = {
    "current_mode": "neutral",
    "active_window_title": "Detecting...",
    "active_process_name": "Detecting...",
    "elapsed_seconds": 0,
    "idle_seconds": 0,
    "tracking_active": True,
    "last_lockout_time": None,
    "last_external_window": "None",
    "last_external_process": "None",
    "last_app_process": None,
    "last_app_title": None,
    "app_accumulated_seconds": 0
}

@app.route("/")
def index():
    # Return index.html from templates
    return send_from_directory(app.template_folder, "index.html")

@app.route("/api/status", methods=["GET"])
def get_status():
    settings = db.get_settings()
    adaptive = db.get_adaptive_times()
    adaptive_work_limit_seconds = adaptive["work_minutes"] * 60
    adaptive_rest_limit_seconds = adaptive["rest_seconds"]
    adaptive_reason = adaptive["reason"]
    work_limit_seconds = settings["work_duration_minutes"] * 60
    
    # Estimate battery level based on daily reflection (optimized with reverse search)
    reflections = db.get_reflections()
    today_str = date.today().isoformat()
    
    current_energy = 5 # Default
    for r in reversed(reflections):
        if r["timestamp"].startswith(today_str):
            current_energy = r["energy_level"]
            break
        try:
            if datetime.fromisoformat(r["timestamp"]).date() < date.today():
                break
        except:
            pass
        
    # Calculate today's total stats (optimized with chronological short-circuiting)
    sessions = db.get_sessions()
    today_work = 0
    today_recharge = 0
    today_rest = 0
    today_bypasses = 0
    
    for s in reversed(sessions):
        if s["start"].startswith(today_str):
            mode = s["mode"]
            duration = s["duration"]
            if mode == "work":
                today_work += duration
            elif mode == "recharge":
                today_recharge += duration
            elif mode == "rest":
                today_rest += duration
            if s.get("bypassed", False):
                today_bypasses += 1
        else:
            try:
                if datetime.fromisoformat(s["start"]).date() < date.today():
                    break
            except:
                pass
                
    # Add ongoing sessions to the totals in real-time
    cur_mode = shared_state["current_mode"]
    elapsed = shared_state["elapsed_seconds"]
    idle = shared_state["idle_seconds"]
    
    if cur_mode == "work":
        today_work += elapsed
    elif cur_mode == "recharge":
        today_recharge += elapsed
    elif cur_mode == "rest":
        today_rest += idle
        
    # Dynamic companion advice generation
    companion_message = "Your cognitive shield is active. Looking good!"
    if not shared_state["tracking_active"]:
        companion_message = "Companion is paused. Take care of yourself out there!"
    elif today_bypasses > 1:
        companion_message = f"That's {today_bypasses} breaks skipped today. Your code can wait; your health shouldn't."
    elif today_bypasses == 1:
        companion_message = "I noticed you skipped a break earlier. No judgment, but let's try to take the next 20-second pause together."
    elif current_energy <= 2:
        companion_message = "Battery critical! Focus blocks are blocked. Please start your recharge/rest."
    elif current_energy == 3:
        companion_message = "Medium energy. Be careful not to push yourself into a hyperfocus trap."
    elif cur_mode == "work":
        companion_message = "Deep work block active. Stay focused, but don't ignore the warning beeps."
    elif cur_mode == "recharge":
        companion_message = "Recharging active. Enjoy the break and clear your head!"
    elif cur_mode == "rest":
        companion_message = "Rest block. Remember to look 20 feet away to relax your eyes."
    else:
        companion_message = "Battery optimal. Keep going, but remember to look away occasionally!"

    return jsonify({
        "current_mode": cur_mode,
        "active_window_title": shared_state["active_window_title"],
        "active_process_name": shared_state["active_process_name"],
        "elapsed_seconds": elapsed,
        "work_limit_seconds": work_limit_seconds,
        "adaptive_work_limit_seconds": adaptive_work_limit_seconds,
        "adaptive_rest_limit_seconds": adaptive_rest_limit_seconds,
        "adaptive_reason": adaptive_reason,
        "idle_seconds": idle,
        "tracking_active": shared_state["tracking_active"],
        "current_energy": current_energy,
        "today_work_seconds": int(today_work),
        "today_recharge_seconds": int(today_recharge),
        "today_rest_seconds": int(today_rest),
        "today_bypasses": today_bypasses,
        "companion_message": companion_message,
        "last_external_window": shared_state["last_external_window"],
        "last_external_process": shared_state["last_external_process"],
        "current_goal": db.get_current_goal(),
        "hydration": db.get_hydration()
    })

@app.route("/api/status/toggle", methods=["POST"])
@require_local_origin
def toggle_tracking():
    data = request.get_json(silent=True) or {}
    enable = data.get("enable", not shared_state["tracking_active"])
    shared_state["tracking_active"] = enable
    return jsonify({"tracking_active": shared_state["tracking_active"]})

@app.route("/api/status/lockout", methods=["POST"])
@require_local_origin
def trigger_manual_lockout():
    shared_state["manual_lockout_requested"] = True
    return jsonify({"status": "success", "message": "Manual lockout triggered"})

@app.route("/api/settings", methods=["GET", "POST"])
@require_local_origin
def manage_settings():
    if request.method == "POST":
        data = request.json or {}
        db.update_settings(data)
        return jsonify({"status": "success", "settings": db.get_settings()})
    else:
        return jsonify(db.get_settings())

@app.route("/api/goal", methods=["GET", "POST"])
@require_local_origin
def manage_goal():
    if request.method == "POST":
        data = request.json or {}
        goal = data.get("goal", "")
        db.set_current_goal(goal)
        return jsonify({"status": "success", "goal": db.get_current_goal()})
    else:
        return jsonify({"goal": db.get_current_goal()})

@app.route("/api/hydration", methods=["GET", "POST"])
@require_local_origin
def manage_hydration():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        cups = data.get("cups")
        delta = data.get("delta")
        if delta is not None:
            try:
                current_amount = db.get_hydration()["cups"]
                new_amount = max(0, float(current_amount) + float(delta))
                res = db.increment_hydration(cups=new_amount)
            except (ValueError, TypeError):
                res = db.get_hydration()
        else:
            res = db.increment_hydration(cups=cups)
        return jsonify({"status": "success", "hydration": res})
    else:
        return jsonify(db.get_hydration())

@app.route("/api/reflections", methods=["GET", "POST"])
@require_local_origin
def manage_reflections():
    if request.method == "POST":
        data = request.json or {}
        energy = data.get("energy_level")
        friction = data.get("friction_level")
        summary = data.get("summary", "")
        
        if energy is None or friction is None:
            return jsonify({"error": "energy_level and friction_level are required"}), 400
        
        # Validate and clamp input ranges
        try:
            energy = max(1, min(5, int(energy)))
            friction = max(1, min(5, int(friction)))
        except (ValueError, TypeError):
            return jsonify({"error": "energy_level and friction_level must be integers 1-5"}), 400
        summary = str(summary).strip()[:500]  # Cap summary length
            
        entry = db.add_reflection(energy, friction, summary)
        return jsonify({"status": "success", "reflection": entry})
    else:
        return jsonify(db.get_reflections())

@app.route("/api/analytics", methods=["GET"])
def get_analytics():
    reflections = db.get_reflections()
    sessions = db.get_sessions()
    app_usage = db.get_app_usage()
    
    settings = db.get_settings()
    work_keywords = settings.get("work_keywords", [])
    recharge_keywords = settings.get("recharge_keywords", [])
    
    # Classification cache to avoid redundant regex matching across thousands of entries
    classification_cache = {}
    
    from datetime import timedelta
    cutoff_date = (date.today() - timedelta(days=8)).isoformat()
    
    processed_app_usage = []
    for entry in app_usage:
        entry_date = entry.get("date", "")
        if entry_date and entry_date < cutoff_date:
            continue
            
        process = entry.get("process", "")
        title = entry.get("title", "")
        titles = entry.get("titles", {})
        
        # Determine category for each title separately
        title_categories = {}
        work_dur = 0
        recharge_dur = 0
        neutral_dur = 0
        
        if titles:
            for t, dur in titles.items():
                cache_key = (process, t)
                if cache_key in classification_cache:
                    cat = classification_cache[cache_key]
                else:
                    cat = "neutral"
                    if any(matches_keyword(kw, process) or matches_keyword(kw, t) for kw in work_keywords):
                        cat = "work"
                    elif any(matches_keyword(kw, process) or matches_keyword(kw, t) for kw in recharge_keywords):
                        cat = "recharge"
                    classification_cache[cache_key] = cat
                
                title_categories[t] = cat
                if cat == "work":
                    work_dur += dur
                elif cat == "recharge":
                    recharge_dur += dur
                else:
                    neutral_dur += dur
        else:
            # Fallback if titles is empty
            cache_key = (process, title)
            if cache_key in classification_cache:
                cat = classification_cache[cache_key]
            else:
                cat = "neutral"
                if any(matches_keyword(kw, process) or matches_keyword(kw, title) for kw in work_keywords):
                    cat = "work"
                elif any(matches_keyword(kw, process) or matches_keyword(kw, title) for kw in recharge_keywords):
                    cat = "recharge"
                classification_cache[cache_key] = cat
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
    
    # Calculate energy vs friction mapping
    energy_levels = [r["energy_level"] for r in reflections]
    friction_levels = [r["friction_level"] for r in reflections]
    
    # Compute average energy and friction per weekday
    weekday_data = {i: {"energy": [], "friction": [], "count": 0} for i in range(7)}
    for r in reflections:
        try:
            dt = datetime.fromisoformat(r["timestamp"])
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

    # Compute high-quality structured premium insights
    insights = []
    
    total_work = 0
    total_rest_recharge = 0
    bypassed_count = 0
    for s in sessions:
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

    # Insight 3: High Friction Hotspots
    high_friction_reflections = [r for r in reflections if r["friction_level"] >= 4]
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
    elif reflections:
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
    settings = db.get_settings()
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

    # Insight 5: Circadian Peak Energy
    time_groups = {"morning": [], "afternoon": [], "evening": [], "night": []}
    for r in reflections:
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
        
    today_str = date.today().isoformat()
    today_sessions = [s for s in sessions if s["start"].startswith(today_str)]

    return jsonify({
        "reflections": reflections[-15:], # Send last 15 for recent list
        "weekday_summary": weekday_summary,
        "recommendations": recommendations,
        "insights": insights,
        "total_reflections": len(reflections),
        "total_sessions": len(sessions),
        "today_sessions": today_sessions,
        "app_usage": processed_app_usage
    })

@app.route("/api/shutdown", methods=["POST"])
@require_local_origin
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
            
    db.log_session(cur_mode, datetime.now(), datetime.now()) # log final block close if any
    
    # Graceful shutdown: flush database and exit cleanly
    def terminate():
        import time
        time.sleep(0.5)
        db.save(sync=True)  # Ensure final data flush before exit
        import os
        os._exit(0)
        
    import threading
    threading.Thread(target=terminate, daemon=True).start()
    return jsonify({"status": "shutdown_initiated"})

def run_server(port=5000):
    # Run flask app on localhost and port 5000
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    run_server()
