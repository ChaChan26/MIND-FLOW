/*
Focus Sprint and Rest Recovery Timer Engine with progress tracking and flow protection.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;

namespace MindFlow.Core.Focus
{
    public enum FocusTimerState
    {
        Idle,
        Running,
        Paused,
        Completed
    }

    public enum FocusSessionType
    {
        Sprint,
        Break
    }

    public class FocusTimerCompletedEventArgs : EventArgs
    {
        public FocusSessionType SessionType { get; }
        public int TotalMinutes { get; }

        public FocusTimerCompletedEventArgs(FocusSessionType sessionType, int totalMinutes)
        {
            SessionType = sessionType;
            TotalMinutes = totalMinutes;
        }
    }

    public class FocusTimerEngine
    {
        public FocusTimerState State { get; private set; } = FocusTimerState.Idle;
        public FocusSessionType SessionType { get; private set; } = FocusSessionType.Sprint;

        public double TotalDurationSeconds { get; private set; } = 25 * 60;
        public double RemainingSeconds { get; private set; } = 25 * 60;

        public event EventHandler<FocusTimerCompletedEventArgs>? SessionCompleted;
        public event EventHandler? TickUpdated;

        public double Progress => TotalDurationSeconds > 0
            ? Math.Clamp(1.0 - (RemainingSeconds / TotalDurationSeconds), 0.0, 1.0)
            : 0.0;

        public string FormattedTime
        {
            get
            {
                int totalSec = (int)Math.Max(0, Math.Ceiling(RemainingSeconds));
                int mins = totalSec / 60;
                int secs = totalSec % 60;
                return $"{mins:D2}:{secs:D2}";
            }
        }

        public bool IsRunning => State == FocusTimerState.Running;
        public bool IsSprint => SessionType == FocusSessionType.Sprint;

        public void StartSprint(int minutes = 25)
        {
            if (minutes <= 0) minutes = 25;
            SessionType = FocusSessionType.Sprint;
            TotalDurationSeconds = minutes * 60.0;
            RemainingSeconds = TotalDurationSeconds;
            State = FocusTimerState.Running;
            TickUpdated?.Invoke(this, EventArgs.Empty);
        }

        public void StartBreak(int minutes = 5)
        {
            if (minutes <= 0) minutes = 5;
            SessionType = FocusSessionType.Break;
            TotalDurationSeconds = minutes * 60.0;
            RemainingSeconds = TotalDurationSeconds;
            State = FocusTimerState.Running;
            TickUpdated?.Invoke(this, EventArgs.Empty);
        }

        public void Pause()
        {
            if (State == FocusTimerState.Running)
            {
                State = FocusTimerState.Paused;
                TickUpdated?.Invoke(this, EventArgs.Empty);
            }
        }

        public void Resume()
        {
            if (State == FocusTimerState.Paused)
            {
                State = FocusTimerState.Running;
                TickUpdated?.Invoke(this, EventArgs.Empty);
            }
        }

        public void Reset()
        {
            State = FocusTimerState.Idle;
            RemainingSeconds = TotalDurationSeconds;
            TickUpdated?.Invoke(this, EventArgs.Empty);
        }

        public bool ProcessTick(double deltaSeconds)
        {
            if (State != FocusTimerState.Running || deltaSeconds <= 0)
            {
                return false;
            }

            RemainingSeconds -= deltaSeconds;

            if (RemainingSeconds <= 0.0)
            {
                RemainingSeconds = 0.0;
                State = FocusTimerState.Completed;
                int mins = (int)Math.Round(TotalDurationSeconds / 60.0);
                SessionCompleted?.Invoke(this, new FocusTimerCompletedEventArgs(SessionType, mins));
                TickUpdated?.Invoke(this, EventArgs.Empty);
                return true;
            }

            TickUpdated?.Invoke(this, EventArgs.Empty);
            return false;
        }
    }
}
