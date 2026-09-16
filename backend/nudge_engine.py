"""
Cognitive Proactive Nudge Engine managing real-time behavioral interventions,
flow-state shields, and system notifications without SQLite write locking.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import sys
import time
import threading

def send_system_notification(title, message, sound_type="asterisk"):
    """Dispatch non-blocking system notification and sound on Windows with zero process overhead."""
    if sys.platform == "win32" and sound_type:
        try:
            import winsound
            if sound_type == "exclamation":
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            elif sound_type == "hand":
                winsound.MessageBeep(winsound.MB_ICONHAND)
            else:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

class CognitiveNudgeEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self.nudge_state = {
            "last_nudges": {},
            "distraction_dwell_start": None,
            "active_work_seconds": 0,
            "active_hydration_seconds": 0,
        }

    def evaluate_proactive_nudges(
        self,
        current_mode,
        target_mode,
        active_process,
        active_title,
        elapsed_seconds,
        work_limit_sec,
        battery_cap,
        is_flow_session,
        idle_sec_val,
        settings,
        context_switch_deque,
        shared_state
    ):
        """
        Evaluates in-memory heuristic triggers and dispatches prioritized proactive nudges
        with rate-limiting cooldowns, flow shield suppression, and zero SQLite locking.
        """
        with self._lock:
            now_sec = time.time()
            proactivity_level = settings.get("proactivity_level", "balanced")
            
            if proactivity_level == "disabled":
                if shared_state.get("active_nudge"):
                    shared_state["active_nudge"] = None
                return

            snooze_until = shared_state.get("nudge_snooze_until", 0.0) or 0.0
            is_snoozed = (now_sec < snooze_until)
            
            # Cooldown parameters per proactivity preset
            if proactivity_level == "strict":
                default_cooldown = 180.0   # 3 mins
                distraction_dwell = 15.0   # 15s
                thrash_threshold = 4
            elif proactivity_level == "gentle":
                default_cooldown = 900.0   # 15 mins
                distraction_dwell = 60.0   # 60s
                thrash_threshold = 8
            else: # balanced (default)
                default_cooldown = 300.0   # 5 mins
                distraction_dwell = 30.0   # 30s
                thrash_threshold = 5

            last_nudges = self.nudge_state.setdefault("last_nudges", {})
            new_nudge = None
            sound_type = "asterisk"

            # Reset eye-care and hydration accumulators when not actively working
            if current_mode != "work":
                self.nudge_state["active_work_seconds"] = 0
                self.nudge_state["active_hydration_seconds"] = 0

            # --- Priority 1: Critical Stamina Depletion (<15%) ---
            if battery_cap <= 15.0 and current_mode == "work":
                if now_sec - last_nudges.get("critical_battery", 0) >= 300.0:
                    new_nudge = {
                        "id": f"crit_battery_{int(now_sec)}",
                        "type": "critical",
                        "title": f"⚡ Critical Stamina Depleted ({int(battery_cap)}%)",
                        "message": "Cognitive stamina is dangerously low. Rest cycle strongly recommended to avoid mental burnout.",
                        "actions": [
                            {"label": "🧘 Start Zen Break", "action": "take_break", "variant": "primary"},
                            {"label": "Dismiss", "action": "dismiss", "variant": "ghost"}
                        ]
                    }
                    sound_type = "hand"
                    last_nudges["critical_battery"] = now_sec

            # If snoozed, suppress remaining non-critical triggers
            if is_snoozed and not new_nudge:
                return

            # --- Flow Shield: Suppress non-critical alerts when deep in flow ---
            if is_flow_session and not new_nudge:
                return

            # --- Priority 2: Sprint Limit Reached ---
            effective_work_limit = work_limit_sec + (shared_state.get("session_extension_seconds", 0) or 0)
            if not new_nudge and current_mode == "work" and elapsed_seconds >= effective_work_limit:
                if now_sec - last_nudges.get("sprint_complete", 0) >= 180.0:
                    new_nudge = {
                        "id": f"sprint_{int(now_sec)}",
                        "type": "info",
                        "title": "🎯 Focus Sprint Complete",
                        "message": f"Completed planned focus block ({int(effective_work_limit / 60)}m). Take a well-earned break or extend focus.",
                        "actions": [
                            {"label": "☕ Take Break", "action": "take_break", "variant": "primary"},
                            {"label": "Extend +5m", "action": "extend_5m", "variant": "secondary"},
                            {"label": "Dismiss", "action": "dismiss", "variant": "ghost"}
                        ]
                    }
                    sound_type = "exclamation"
                    last_nudges["sprint_complete"] = now_sec

            # --- Priority 3: Low Battery Warning (<30%) ---
            if not new_nudge and current_mode == "work" and battery_cap <= 30.0:
                if now_sec - last_nudges.get("low_battery", 0) >= default_cooldown:
                    new_nudge = {
                        "id": f"low_battery_{int(now_sec)}",
                        "type": "warning",
                        "title": f"🔋 Cognitive Battery Low ({int(battery_cap)}%)",
                        "message": "Focus efficiency is dropping. Consider wrapping up complex tasks or starting a short recharge.",
                        "actions": [
                            {"label": "Take 5m Break", "action": "take_break", "variant": "primary"},
                            {"label": "Snooze 15m", "action": "snooze", "variant": "ghost"}
                        ]
                    }
                    sound_type = "asterisk"
                    last_nudges["low_battery"] = now_sec

            # --- Priority 4: Distraction Drift (with Dwell Grace Period) ---
            if not new_nudge and settings.get("enable_distraction_nudges", True) and current_mode == "work" and target_mode in ("recharge", "rest"):
                dwell_start = self.nudge_state.get("distraction_dwell_start")
                if dwell_start is None:
                    self.nudge_state["distraction_dwell_start"] = now_sec
                elif now_sec - dwell_start >= distraction_dwell:
                    if now_sec - last_nudges.get("distraction_drift", 0) >= default_cooldown:
                        new_nudge = {
                            "id": f"drift_{int(now_sec)}",
                            "type": "warning",
                            "title": f"⚠️ Distraction Drift: {active_process or 'App'}",
                            "message": "Recharge application active during work sprint. Transition to recharge mode or refocus on tasks?",
                            "actions": [
                                {"label": "Switch to Recharge", "action": "switch_to_recharge", "variant": "primary"},
                                {"label": "Refocus (+5m)", "action": "extend_5m", "variant": "secondary"},
                                {"label": "Dismiss", "action": "dismiss", "variant": "ghost"}
                            ]
                        }
                        sound_type = "exclamation"
                        last_nudges["distraction_drift"] = now_sec
            elif target_mode not in ("recharge", "rest"):
                self.nudge_state["distraction_dwell_start"] = None

            # --- Priority 5: Context Switch Thrashing ---
            if not new_nudge and settings.get("enable_thrashing_nudges", True) and current_mode == "work":
                recent_switches = len([t for t in context_switch_deque if now_sec - t <= 120.0])
                if recent_switches >= thrash_threshold:
                    if now_sec - last_nudges.get("thrashing", 0) >= default_cooldown:
                        new_nudge = {
                            "id": f"thrash_{int(now_sec)}",
                            "type": "warning",
                            "title": "⚡ High Cognitive Friction Detected",
                            "message": f"{recent_switches} rapid window switches in 2 mins. Single-tasking or a 2-minute reset is recommended.",
                            "actions": [
                                {"label": "Take 2m Reset", "action": "take_break", "variant": "primary"},
                                {"label": "Snooze 15m", "action": "snooze", "variant": "ghost"}
                            ]
                        }
                        sound_type = "asterisk"
                        last_nudges["thrashing"] = now_sec

            # --- Priority 6: 20-20-20 Eye Care Nudge (Every 20m active work) ---
            if not new_nudge and settings.get("enable_eyecare_nudges", True) and current_mode == "work" and idle_sec_val < 5:
                active_work_sec = self.nudge_state.get("active_work_seconds", 0) + 1
                self.nudge_state["active_work_seconds"] = active_work_sec
                if active_work_sec >= 1200: # 20 minutes
                    if now_sec - last_nudges.get("eyecare", 0) >= 1200.0:
                        new_nudge = {
                            "id": f"eyecare_{int(now_sec)}",
                            "type": "info",
                            "title": "👁️ 20-20-20 Eye Rest",
                            "message": "Look at an object 20 feet away for 20 seconds to relax your eye ciliary muscles.",
                            "actions": [
                                {"label": "Done", "action": "dismiss", "variant": "primary"},
                                {"label": "Snooze 15m", "action": "snooze", "variant": "ghost"}
                            ]
                        }
                        sound_type = "asterisk"
                        last_nudges["eyecare"] = now_sec
                        self.nudge_state["active_work_seconds"] = 0

            # --- Priority 7: Hydration Nudge (Every 60m active work) ---
            if not new_nudge and settings.get("enable_hydration_nudges", True) and current_mode == "work" and idle_sec_val < 5:
                active_hydration_sec = self.nudge_state.get("active_hydration_seconds", 0) + 1
                self.nudge_state["active_hydration_seconds"] = active_hydration_sec
                if active_hydration_sec >= 3600: # 60 minutes
                    if now_sec - last_nudges.get("hydration", 0) >= 3600.0:
                        new_nudge = {
                            "id": f"hydration_{int(now_sec)}",
                            "type": "info",
                            "title": "💧 Hydration Reminder",
                            "message": "Stay energized and maintain cognitive speed by drinking a glass of water.",
                            "actions": [
                                {"label": "Drink Water (+1)", "action": "drink_water", "variant": "primary"},
                                {"label": "Snooze 15m", "action": "snooze", "variant": "ghost"}
                            ]
                        }
                        sound_type = "asterisk"
                        last_nudges["hydration"] = now_sec
                        self.nudge_state["active_hydration_seconds"] = 0

            if new_nudge:
                shared_state["active_nudge"] = new_nudge
                play_sound = sound_type if settings.get("enable_audio_chimes", True) else None
                if settings.get("enable_desktop_toasts", True) or settings.get("enable_audio_chimes", True):
                    send_system_notification(new_nudge["title"], new_nudge["message"], play_sound)

_default_nudge_engine = CognitiveNudgeEngine()

def evaluate_proactive_nudges(
    current_mode,
    target_mode,
    active_process,
    active_title,
    elapsed_seconds,
    work_limit_sec,
    battery_cap,
    is_flow_session,
    idle_sec_val,
    settings,
    context_switch_deque,
    nudge_state,
    shared_state
):
    """Module-level bridge for evaluating proactive nudges with state dict support."""
    if not hasattr(evaluate_proactive_nudges, "_engine"):
        evaluate_proactive_nudges._engine = CognitiveNudgeEngine()
    if nudge_state:
        evaluate_proactive_nudges._engine.nudge_state = nudge_state
    evaluate_proactive_nudges._engine.evaluate_proactive_nudges(
        current_mode=current_mode,
        target_mode=target_mode,
        active_process=active_process,
        active_title=active_title,
        elapsed_seconds=elapsed_seconds,
        work_limit_sec=work_limit_sec,
        battery_cap=battery_cap,
        is_flow_session=is_flow_session,
        idle_sec_val=idle_sec_val,
        settings=settings,
        context_switch_deque=context_switch_deque,
        shared_state=shared_state
    )

