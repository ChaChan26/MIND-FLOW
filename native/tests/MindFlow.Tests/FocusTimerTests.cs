/*
Unit tests validating focus sprint and rest break timer engine transitions, progress math, and event notifications.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using MindFlow.Core.Focus;
using Xunit;

namespace MindFlow.Tests
{
    public class FocusTimerTests
    {
        [Fact]
        public void FocusTimer_StartSprint_InitializesRemainingAndDuration()
        {
            var engine = new FocusTimerEngine();
            engine.StartSprint(25);

            Assert.Equal(FocusTimerState.Running, engine.State);
            Assert.Equal(FocusSessionType.Sprint, engine.SessionType);
            Assert.True(engine.IsRunning);
            Assert.True(engine.IsSprint);
            Assert.Equal(1500.0, engine.TotalDurationSeconds);
            Assert.Equal(1500.0, engine.RemainingSeconds);
            Assert.Equal(0.0, engine.Progress);
            Assert.Equal("25:00", engine.FormattedTime);
        }

        [Fact]
        public void FocusTimer_ProcessTick_DecrementsRemainingAndComputesProgress()
        {
            var engine = new FocusTimerEngine();
            engine.StartSprint(25);

            // Tick 30 seconds
            bool completed = engine.ProcessTick(30.0);

            Assert.False(completed);
            Assert.Equal(1470.0, engine.RemainingSeconds);
            Assert.Equal("24:30", engine.FormattedTime);
            Assert.Equal(30.0 / 1500.0, engine.Progress, precision: 4);
        }

        [Fact]
        public void FocusTimer_PauseAndResume_TogglesRunningState()
        {
            var engine = new FocusTimerEngine();
            engine.StartSprint(25);

            engine.Pause();
            Assert.Equal(FocusTimerState.Paused, engine.State);
            Assert.False(engine.IsRunning);

            // Processing ticks while paused must not decrement remaining time
            bool ticked = engine.ProcessTick(10.0);
            Assert.False(ticked);
            Assert.Equal(1500.0, engine.RemainingSeconds);

            engine.Resume();
            Assert.Equal(FocusTimerState.Running, engine.State);
            Assert.True(engine.IsRunning);
        }

        [Fact]
        public void FocusTimer_Reset_ReturnsToIdle()
        {
            var engine = new FocusTimerEngine();
            engine.StartSprint(25);
            engine.ProcessTick(500.0);

            engine.Reset();

            Assert.Equal(FocusTimerState.Idle, engine.State);
            Assert.False(engine.IsRunning);
            Assert.Equal(1500.0, engine.RemainingSeconds);
            Assert.Equal(0.0, engine.Progress);
        }

        [Fact]
        public void FocusTimer_CountdownCompletion_FiresSessionCompletedEvent()
        {
            var engine = new FocusTimerEngine();
            engine.StartSprint(25);

            bool eventFired = false;
            FocusSessionType? completedType = null;
            int completedMins = 0;

            engine.SessionCompleted += (sender, e) =>
            {
                eventFired = true;
                completedType = e.SessionType;
                completedMins = e.TotalMinutes;
            };

            // Fast-forward tick past the end
            bool completed = engine.ProcessTick(1501.0);

            Assert.True(completed);
            Assert.True(eventFired);
            Assert.Equal(FocusSessionType.Sprint, completedType);
            Assert.Equal(25, completedMins);
            Assert.Equal(FocusTimerState.Completed, engine.State);
            Assert.Equal(0.0, engine.RemainingSeconds);
            Assert.Equal(1.0, engine.Progress);
            Assert.Equal("00:00", engine.FormattedTime);
        }

        [Fact]
        public void FocusTimer_StartBreak_SetsBreakSessionType()
        {
            var engine = new FocusTimerEngine();
            engine.StartBreak(5);

            Assert.Equal(FocusTimerState.Running, engine.State);
            Assert.Equal(FocusSessionType.Break, engine.SessionType);
            Assert.False(engine.IsSprint);
            Assert.Equal(300.0, engine.TotalDurationSeconds);
            Assert.Equal(300.0, engine.RemainingSeconds);
            Assert.Equal("05:00", engine.FormattedTime);
        }
    }
}
