/*
Cognitive Proactive Nudge Engine managing real-time behavioral interventions,
flow-state shields, and system notifications without database write locking.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Collections.Generic;
using System.Linq;
using MindFlow.Core.Classification;

namespace MindFlow.Core.Nudges
{
    public class CognitiveNudgeEngine
    {
        private readonly object _lock = new();
        private readonly Dictionary<string, double> _lastNudges = new();
        private double? _distractionDwellStart = null;
        private double _activeWorkSeconds = 0;
        private double _activeHydrationSeconds = 0;

        public double SnoozeUntilSec { get; set; } = 0.0;
        public NudgeNotification? ActiveNudge { get; private set; }

        public NudgeNotification? EvaluateProactiveNudges(
            ActivityMode currentMode,
            ActivityMode targetMode,
            string activeProcess,
            string activeTitle,
            double elapsedSeconds,
            double workLimitSec,
            double batteryCap,
            bool isFlowSession,
            double idleSecVal,
            NudgeSettings settings,
            IReadOnlyCollection<double> contextSwitchTimestamps,
            double currentTimestampSec = 0.0)
        {
            lock (_lock)
            {
                double nowSec = currentTimestampSec > 0
                    ? currentTimestampSec
                    : DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;

                string proactivity = (settings.ProactivityLevel ?? "balanced").ToLowerInvariant();
                if (proactivity == "disabled")
                {
                    ActiveNudge = null;
                    return null;
                }

                bool isSnoozed = (nowSec < SnoozeUntilSec);

                double defaultCooldown;
                double distractionDwell;
                int thrashThreshold;

                if (proactivity == "strict")
                {
                    defaultCooldown = 180.0;
                    distractionDwell = 15.0;
                    thrashThreshold = 4;
                }
                else if (proactivity == "gentle")
                {
                    defaultCooldown = 900.0;
                    distractionDwell = 60.0;
                    thrashThreshold = 8;
                }
                else // balanced
                {
                    defaultCooldown = 300.0;
                    distractionDwell = 30.0;
                    thrashThreshold = 5;
                }

                bool HasCooldownElapsed(string key, double cooldownSec)
                {
                    if (!_lastNudges.TryGetValue(key, out double lastTime))
                        return true;
                    return (nowSec - lastTime) >= cooldownSec;
                }

                NudgeNotification? newNudge = null;

                // Reset eye-care and hydration counters if not actively working
                if (currentMode != ActivityMode.Work)
                {
                    _activeWorkSeconds = 0;
                    _activeHydrationSeconds = 0;
                }

                // --- Priority 1: Critical Stamina Depletion (<15%) ---
                if (batteryCap <= 15.0 && currentMode == ActivityMode.Work)
                {
                    if (HasCooldownElapsed("critical_battery", 300.0))
                    {
                        newNudge = new NudgeNotification(
                            Id: $"crit_battery_{(long)nowSec}",
                            Severity: NudgeSeverity.Critical,
                            Title: $"⚡ Critical Stamina Depleted ({(int)batteryCap}%)",
                            Message: "Cognitive stamina is dangerously low. Rest cycle strongly recommended to avoid mental burnout.",
                            SoundType: "hand",
                            Actions: new List<NudgeAction>
                            {
                                new("🧘 Start Zen Break", "take_break", "primary"),
                                new("Dismiss", "dismiss", "ghost")
                            },
                            CreatedAt: DateTime.UtcNow);

                        _lastNudges["critical_battery"] = nowSec;
                    }
                }

                // If snoozed, suppress remaining non-critical triggers
                if (isSnoozed && newNudge == null)
                {
                    return null;
                }

                // --- Flow Shield: Suppress non-critical alerts when deep in flow ---
                if (isFlowSession && newNudge == null)
                {
                    return null;
                }

                // --- Priority 2: Sprint Limit Reached ---
                if (newNudge == null && currentMode == ActivityMode.Work && elapsedSeconds >= workLimitSec)
                {
                    if (HasCooldownElapsed("sprint_complete", 180.0))
                    {
                        newNudge = new NudgeNotification(
                            Id: $"sprint_{(long)nowSec}",
                            Severity: NudgeSeverity.Info,
                            Title: "🎯 Focus Sprint Complete",
                            Message: $"Completed planned focus block ({(int)(workLimitSec / 60)}m). Take a well-earned break or extend focus.",
                            SoundType: "exclamation",
                            Actions: new List<NudgeAction>
                            {
                                new("☕ Take Break", "take_break", "primary"),
                                new("Extend +5m", "extend_5m", "secondary"),
                                new("Dismiss", "dismiss", "ghost")
                            },
                            CreatedAt: DateTime.UtcNow);

                        _lastNudges["sprint_complete"] = nowSec;
                    }
                }

                // --- Priority 3: Low Battery Warning (<30%) ---
                if (newNudge == null && currentMode == ActivityMode.Work && batteryCap <= 30.0)
                {
                    if (HasCooldownElapsed("low_battery", defaultCooldown))
                    {
                        newNudge = new NudgeNotification(
                            Id: $"low_battery_{(long)nowSec}",
                            Severity: NudgeSeverity.Warning,
                            Title: $"🔋 Cognitive Battery Low ({(int)batteryCap}%)",
                            Message: "Focus efficiency is dropping. Consider wrapping up complex tasks or starting a short recharge.",
                            SoundType: "asterisk",
                            Actions: new List<NudgeAction>
                            {
                                new("Take 5m Break", "take_break", "primary"),
                                new("Snooze 15m", "snooze", "ghost")
                            },
                            CreatedAt: DateTime.UtcNow);

                        _lastNudges["low_battery"] = nowSec;
                    }
                }

                // --- Priority 4: Distraction Drift (with Dwell Grace Period) ---
                if (newNudge == null && settings.EnableDistractionNudges && currentMode == ActivityMode.Work &&
                    targetMode is ActivityMode.Recharge or ActivityMode.Rest)
                {
                    if (_distractionDwellStart == null)
                    {
                        _distractionDwellStart = nowSec;
                    }
                    else if (nowSec - _distractionDwellStart.Value >= distractionDwell)
                    {
                        if (HasCooldownElapsed("distraction_drift", defaultCooldown))
                        {
                            newNudge = new NudgeNotification(
                                Id: $"drift_{(long)nowSec}",
                                Severity: NudgeSeverity.Warning,
                                Title: $"⚠️ Distraction Drift: {activeProcess ?? "App"}",
                                Message: "Recharge application active during work sprint. Transition to recharge mode or refocus on tasks?",
                                SoundType: "exclamation",
                                Actions: new List<NudgeAction>
                                {
                                    new("Switch to Recharge", "switch_to_recharge", "primary"),
                                    new("Refocus (+5m)", "extend_5m", "secondary"),
                                    new("Dismiss", "dismiss", "ghost")
                                },
                                CreatedAt: DateTime.UtcNow);

                            _lastNudges["distraction_drift"] = nowSec;
                        }
                    }
                }
                else if (targetMode is not (ActivityMode.Recharge or ActivityMode.Rest))
                {
                    _distractionDwellStart = null;
                }

                // --- Priority 5: Context Switch Thrashing ---
                if (newNudge == null && settings.EnableThrashingNudges && currentMode == ActivityMode.Work)
                {
                    int recentSwitches = contextSwitchTimestamps.Count(t => nowSec - t <= 120.0);
                    if (recentSwitches >= thrashThreshold)
                    {
                        if (HasCooldownElapsed("thrashing", defaultCooldown))
                        {
                            newNudge = new NudgeNotification(
                                Id: $"thrash_{(long)nowSec}",
                                Severity: NudgeSeverity.Warning,
                                Title: "⚡ High Cognitive Friction Detected",
                                Message: $"{recentSwitches} rapid window switches in 2 mins. Single-tasking or a 2-minute reset is recommended.",
                                SoundType: "asterisk",
                                Actions: new List<NudgeAction>
                                {
                                    new("Take 2m Reset", "take_break", "primary"),
                                    new("Snooze 15m", "snooze", "ghost")
                                },
                                CreatedAt: DateTime.UtcNow);

                            _lastNudges["thrashing"] = nowSec;
                        }
                    }
                }

                // --- Priority 6: 20-20-20 Eye Care Nudge (Every 20m active work) ---
                if (newNudge == null && settings.EnableEyeCareNudges && currentMode == ActivityMode.Work && idleSecVal < 5.0)
                {
                    _activeWorkSeconds += 1.0;
                    if (_activeWorkSeconds >= 1200.0) // 20 minutes
                    {
                        if (HasCooldownElapsed("eyecare", 1200.0))
                        {
                            newNudge = new NudgeNotification(
                                Id: $"eyecare_{(long)nowSec}",
                                Severity: NudgeSeverity.Info,
                                Title: "👁️ 20-20-20 Eye Rest",
                                Message: "Look at an object 20 feet away for 20 seconds to relax your eye ciliary muscles.",
                                SoundType: "asterisk",
                                Actions: new List<NudgeAction>
                                {
                                    new("Done", "dismiss", "primary"),
                                    new("Snooze 15m", "snooze", "ghost")
                                },
                                CreatedAt: DateTime.UtcNow);

                            _lastNudges["eyecare"] = nowSec;
                            _activeWorkSeconds = 0;
                        }
                    }
                }

                // --- Priority 7: Hydration Nudge (Every 60m active work) ---
                if (newNudge == null && settings.EnableHydrationNudges && currentMode == ActivityMode.Work && idleSecVal < 5.0)
                {
                    _activeHydrationSeconds += 1.0;
                    if (_activeHydrationSeconds >= 3600.0) // 60 minutes
                    {
                        if (HasCooldownElapsed("hydration", 3600.0))
                        {
                            newNudge = new NudgeNotification(
                                Id: $"hydration_{(long)nowSec}",
                                Severity: NudgeSeverity.Info,
                                Title: "💧 Hydration Reminder",
                                Message: "Stay energized and maintain cognitive speed by drinking a glass of water.",
                                SoundType: "asterisk",
                                Actions: new List<NudgeAction>
                                {
                                    new("Drink Water (+1)", "drink_water", "primary"),
                                    new("Snooze 15m", "snooze", "ghost")
                                },
                                CreatedAt: DateTime.UtcNow);

                            _lastNudges["hydration"] = nowSec;
                            _activeHydrationSeconds = 0;
                        }
                    }
                }

                if (newNudge != null)
                {
                    ActiveNudge = newNudge;
                }

                return newNudge;
            }
        }

        public void Snooze(double durationSeconds = 900.0)
        {
            lock (_lock)
            {
                double nowSec = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;
                SnoozeUntilSec = nowSec + durationSeconds;
                ActiveNudge = null;
            }
        }

        public void DismissActiveNudge()
        {
            lock (_lock)
            {
                ActiveNudge = null;
            }
        }
    }
}
