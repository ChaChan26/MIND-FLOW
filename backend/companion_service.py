"""
Companion messaging and forecast service for MIND-FLOW.
Generates contextual companion messages, CBT mental health advice,
and battery depletion/recharge forecasts.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

from typing import Optional, Dict, Any


def generate_companion_message(
    tracking_active: bool,
    today_bypasses: int,
    high_stress_alert: bool,
    latest_mood: Optional[str],
    current_energy: float,
    cur_mode: str
) -> str:
    """Generate dynamic companion advice with CBT mental health interventions."""
    if not tracking_active:
        return "Companion is paused. Take care of yourself out there!"
    if today_bypasses > 1:
        return f"🚨 That's {today_bypasses} breaks skipped today! Your health comes first: Rest more, step away from the keyboard, and take a physical break."
    if today_bypasses == 1:
        return "⚠️ I noticed you skipped a break earlier. Rest more during the next cycle: stretch your arms and rest your eyes."
    if high_stress_alert:
        return "🚨 Persistent high stress detected! MIND-FLOW has scheduled a deep recovery break. Step away, close your eyes, and take a long rest."
    if latest_mood and latest_mood.lower() in ["anxious", "overwhelmed", "frustrated", "exhausted"]:
        mood_lower = latest_mood.lower()
        if mood_lower == "anxious":
            return "😟 Anxious mood logged. Breathe slowly. Remember, your worth is not defined by today's output."
        elif mood_lower == "overwhelmed":
            return "🤯 Feeling overwhelmed? Focus on a single micro-goal. You have the right to close your tabs and rest."
        elif mood_lower == "frustrated":
            return "😤 Frustration is just a signal to pause. A short walk or water break often unlocks the solution."
        elif mood_lower == "exhausted":
            return "😴 Exhaustion detected. Give yourself permission to log off early or start a rest block."
    if current_energy <= 2:
        return "🔋 Battery critical! Focus blocks are blocked. Rest more, start your rest cycle, and let your mind drift in Zen Space."
    if current_energy <= 3:
        return "🌿 Medium energy. Rest more before you reach exhaustion. Pace yourself and take a deep, mindful breath."
    if cur_mode == "work":
        return "💻 Focus session active. Remember: to sustain this, plan to rest more during upcoming recharge blocks!"
    if cur_mode == "recharge":
        return "🎮 Recharging active. Rest more by looking away from all screens, stretching, or drinking water."
    if cur_mode == "rest":
        return "💤 Rest block. Close your eyes, rest more, and follow the 20-20-20 rule to relax your eyes."
    return "🌳 Energy optimal. Maintain your stamina by remembering to stretch, hydrate, and rest more periodically."


def calculate_battery_forecast(
    cur_mode: str,
    battery_cap: float,
    adaptive_rest_limit_seconds: int,
    base_alert_message: str = ""
) -> str:
    """Calculate dynamic battery depletion and recovery forecast string."""
    if cur_mode == "work" and battery_cap > 0:
        minutes_left = int(battery_cap / 0.5)
        base_forecast = f"Forecast: Battery will deplete in ~{minutes_left} minutes of focus."
    elif cur_mode in ["recharge", "rest"] and battery_cap < 100:
        minutes_left = int((100 - battery_cap) / 2.5)
        base_forecast = f"Forecast: Fully charged battery expected in ~{minutes_left} minutes."
    elif battery_cap <= 0:
        base_forecast = f"Warning: Cognitive stamina depleted. Recommend a rest cycle of {adaptive_rest_limit_seconds} seconds."
    else:
        base_forecast = "Forecast: Stamina optimal. Pace your sprints to sustain focus."
        
    return base_forecast + (base_alert_message or "")

