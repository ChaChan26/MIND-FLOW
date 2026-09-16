/*
Unit tests validating context switch tracking, rolling window rate calculations, and friction level metrics.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using MindFlow.Core.Telemetry;
using Xunit;

namespace MindFlow.Tests
{
    public class ContextSwitchTests
    {
        [Fact]
        public void ContextSwitch_SameProcess_Ignored()
        {
            var tracker = new ContextSwitchTracker();

            bool recorded = tracker.RecordSwitch("code.exe", "code.exe");
            Assert.False(recorded);
            Assert.Equal(0, tracker.TotalSwitchesToday);
            Assert.Equal(0, tracker.SwitchesLast15Minutes);
            Assert.Equal(0.0, tracker.SwitchesPerMinute);
            Assert.Equal(SwitchFrictionLevel.Low, tracker.FrictionLevel);
        }

        [Fact]
        public void ContextSwitch_NullOrWhitespace_Ignored()
        {
            var tracker = new ContextSwitchTracker();

            Assert.False(tracker.RecordSwitch("", "code.exe"));
            Assert.False(tracker.RecordSwitch("code.exe", "   "));
            Assert.Equal(0, tracker.TotalSwitchesToday);
        }

        [Fact]
        public void ContextSwitch_DifferentProcess_RecordsAndIncrements()
        {
            var tracker = new ContextSwitchTracker();

            bool recorded = tracker.RecordSwitch("code.exe", "chrome.exe");
            Assert.True(recorded);
            Assert.Equal(1, tracker.TotalSwitchesToday);
            Assert.Equal(1, tracker.SwitchesLast15Minutes);
            Assert.Equal(1.0 / 15.0, tracker.SwitchesPerMinute, precision: 4);
        }

        [Fact]
        public void ContextSwitch_RollingWindow_PrunesOldSwitches()
        {
            var tracker = new ContextSwitchTracker();
            DateTime now = DateTime.UtcNow;

            // Switch 20 minutes ago (should be pruned on evaluation)
            tracker.RecordSwitch("code.exe", "chrome.exe", now.AddMinutes(-20));

            // Switch 5 minutes ago (should stay in 15-minute window)
            tracker.RecordSwitch("chrome.exe", "slack.exe", now.AddMinutes(-5));

            // Query using current timestamp context
            Assert.Equal(2, tracker.TotalSwitchesToday);
            Assert.Equal(1, tracker.SwitchesLast15Minutes);
        }

        [Fact]
        public void ContextSwitch_FrictionLevel_CalculatesCorrectly()
        {
            var tracker = new ContextSwitchTracker();
            DateTime now = DateTime.UtcNow;

            // Low friction (<0.5 switches/min -> <7.5 switches in 15 mins)
            for (int i = 0; i < 4; i++)
            {
                tracker.RecordSwitch($"proc{i}.exe", $"proc{i + 1}.exe", now.AddMinutes(-i));
            }
            Assert.Equal(SwitchFrictionLevel.Low, tracker.FrictionLevel);
            Assert.Contains("Deep Focus", tracker.FrictionLevelFormatted);

            // Moderate friction (0.5 to 1.5 switches/min -> 8 to 22 switches in 15 mins)
            for (int i = 4; i < 15; i++)
            {
                tracker.RecordSwitch($"proc{i}.exe", $"proc{i + 1}.exe", now.AddMinutes(-1));
            }
            Assert.Equal(SwitchFrictionLevel.Moderate, tracker.FrictionLevel);
            Assert.Contains("Active Multitasking", tracker.FrictionLevelFormatted);

            // High friction (>1.5 switches/min -> >22.5 switches in 15 mins)
            for (int i = 15; i < 30; i++)
            {
                tracker.RecordSwitch($"proc{i}.exe", $"proc{i + 1}.exe", now.AddSeconds(-30));
            }
            Assert.Equal(SwitchFrictionLevel.High, tracker.FrictionLevel);
            Assert.Contains("Fragmented Focus", tracker.FrictionLevelFormatted);
        }

        [Fact]
        public void ContextSwitch_DayRollover_ResetsDailyCounter()
        {
            var tracker = new ContextSwitchTracker();
            DateTime yesterday = DateTime.UtcNow.Date.AddDays(-1).AddHours(12);

            tracker.RecordSwitch("app1.exe", "app2.exe", yesterday);
            Assert.Equal(1, tracker.TotalSwitchesToday);

            // Record a switch today
            DateTime today = DateTime.UtcNow;
            tracker.RecordSwitch("app2.exe", "app3.exe", today);

            // Yesterday's daily total is reset, only today's switch counts
            Assert.Equal(1, tracker.TotalSwitchesToday);
        }
    }
}
