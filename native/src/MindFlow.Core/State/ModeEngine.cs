/*
Mode Transition Engine with hysteresis, distraction dwell grace periods, and manual override locks.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using MindFlow.Core.Classification;

namespace MindFlow.Core.State
{
    public class ModeChangedEventArgs : EventArgs
    {
        public ActivityMode OldMode { get; }
        public ActivityMode NewMode { get; }
        public DateTime Timestamp { get; }
        public bool IsManual { get; }
        public bool WasFlow { get; }
        public double DurationSeconds { get; }

        public ModeChangedEventArgs(ActivityMode oldMode, ActivityMode newMode, DateTime timestamp, bool isManual, bool wasFlow, double durationSeconds)
        {
            OldMode = oldMode;
            NewMode = newMode;
            Timestamp = timestamp;
            IsManual = isManual;
            WasFlow = wasFlow;
            DurationSeconds = durationSeconds;
        }
    }

    public class ModeEngine
    {
        public ActivityMode CurrentMode { get; private set; } = ActivityMode.Neutral;
        public DateTime ModeStartTime { get; private set; } = DateTime.UtcNow;
        public DateTime? ManualOverrideUntil { get; private set; } = null;

        public ProactivityLevel Proactivity { get; set; } = ProactivityLevel.Balanced;
        public double IdleTimeoutSeconds { get; set; } = 180.0;

        private DateTime? _pendingRechargeSince = null;
        private double _continuousWorkSeconds = 0.0;
        public bool IsCurrentFlowSession { get; private set; } = false;

        public event EventHandler<ModeChangedEventArgs>? ModeChanged;

        public ModeEngine(ActivityMode initialMode = ActivityMode.Neutral)
        {
            CurrentMode = initialMode;
            ModeStartTime = DateTime.UtcNow;
        }

        public void SetManualMode(ActivityMode targetMode, int overrideDurationSeconds = 120)
        {
            ManualOverrideUntil = DateTime.UtcNow.AddSeconds(overrideDurationSeconds);
            _pendingRechargeSince = null;
            TransitionTo(targetMode, isManual: true);
        }

        public void ClearManualOverride()
        {
            ManualOverrideUntil = null;
        }

        public void EvaluateTick(
            ActivityMode classifiedMode,
            double idleSeconds,
            double deltaSeconds)
        {
            DateTime now = DateTime.UtcNow;

            // 1. Idle Detection Trigger
            if (idleSeconds >= IdleTimeoutSeconds && CurrentMode != ActivityMode.Rest)
            {
                // When idle timeout reached, transition to Rest regardless of manual locks
                TransitionTo(ActivityMode.Rest, isManual: false);
                return;
            }

            // If we are in Rest mode and user resumes physical activity
            if (CurrentMode == ActivityMode.Rest && idleSeconds < 2.0)
            {
                TransitionTo(classifiedMode == ActivityMode.Rest ? ActivityMode.Neutral : classifiedMode, isManual: false);
                return;
            }

            // 2. Manual Override Guard
            if (ManualOverrideUntil.HasValue && now < ManualOverrideUntil.Value)
            {
                // Locked under user manual sprint/cooldown
                UpdateFlowState(deltaSeconds, idleSeconds);
                return;
            }

            // 3. Distraction Dwell Grace Period (Work -> Recharge)
            if (CurrentMode == ActivityMode.Work && classifiedMode == ActivityMode.Recharge)
            {
                if (!_pendingRechargeSince.HasValue)
                {
                    _pendingRechargeSince = now;
                }

                double graceSeconds = Proactivity switch
                {
                    ProactivityLevel.Strict => 15.0,
                    ProactivityLevel.Balanced => 30.0,
                    ProactivityLevel.Gentle => 60.0,
                    _ => 30.0
                };

                if ((now - _pendingRechargeSince.Value).TotalSeconds >= graceSeconds)
                {
                    _pendingRechargeSince = null;
                    TransitionTo(ActivityMode.Recharge, isManual: false);
                }
                else
                {
                    // Still in grace period, maintain Work
                    UpdateFlowState(deltaSeconds, idleSeconds);
                }
                return;
            }
            else
            {
                _pendingRechargeSince = null;
            }

            // 4. Standard Mode Transition
            if (classifiedMode != CurrentMode && classifiedMode != ActivityMode.Neutral)
            {
                TransitionTo(classifiedMode, isManual: false);
            }
            else
            {
                UpdateFlowState(deltaSeconds, idleSeconds);
            }
        }

        private void UpdateFlowState(double deltaSeconds, double idleSeconds)
        {
            if (CurrentMode == ActivityMode.Work)
            {
                if (idleSeconds < 5.0)
                {
                    _continuousWorkSeconds += deltaSeconds;
                    if (_continuousWorkSeconds >= 900.0) // 15 minutes
                    {
                        IsCurrentFlowSession = true;
                    }
                }
            }
            else
            {
                _continuousWorkSeconds = 0.0;
                IsCurrentFlowSession = false;
            }
        }

        private void TransitionTo(ActivityMode newMode, bool isManual)
        {
            if (newMode == CurrentMode) return;

            DateTime now = DateTime.UtcNow;
            double durationSec = (now - ModeStartTime).TotalSeconds;
            bool wasFlow = IsCurrentFlowSession;
            ActivityMode oldMode = CurrentMode;

            CurrentMode = newMode;
            ModeStartTime = now;
            _continuousWorkSeconds = 0.0;
            IsCurrentFlowSession = false;

            ModeChanged?.Invoke(this, new ModeChangedEventArgs(oldMode, newMode, now, isManual, wasFlow, durationSec));
        }
    }
}
