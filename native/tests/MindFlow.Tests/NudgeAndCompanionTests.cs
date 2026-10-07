/*
Unit tests validating CompanionService CBT messages and CognitiveNudgeEngine heuristic priorities.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Collections.Generic;
using Xunit;
using MindFlow.Core.Classification;
using MindFlow.Core.Companion;
using MindFlow.Core.Nudges;

namespace MindFlow.Tests
{
    public class NudgeAndCompanionTests
    {
        [Fact]
        public void CompanionService_GenerateMessage_HandlesCriticalBattery()
        {
            string msg = CompanionService.GenerateCompanionMessage(
                trackingActive: true,
                todayBypasses: 0,
                highStressAlert: false,
                latestMood: null,
                currentEnergy: 25.0,
                curMode: "work");

            Assert.Contains("Battery critical", msg);
        }

        [Fact]
        public void CompanionService_GenerateMessage_RespectsMoodInterventions()
        {
            string msgAnxious = CompanionService.GenerateCompanionMessage(
                trackingActive: true,
                todayBypasses: 0,
                highStressAlert: false,
                latestMood: "anxious",
                currentEnergy: 75.0,
                curMode: "work");

            Assert.Contains("Anxious mood logged", msgAnxious);
        }

        [Fact]
        public void CompanionService_CalculateForecast_ComputesDepletionTime()
        {
            string forecast = CompanionService.CalculateBatteryForecast(
                curMode: "work",
                batteryCap: 50.0,
                adaptiveRestLimitSeconds: 300);

            Assert.Contains("~100 minutes of focus", forecast);
        }

        [Fact]
        public void CognitiveNudgeEngine_Priority1_TriggersOnCriticalBattery()
        {
            var engine = new CognitiveNudgeEngine();
            var settings = new NudgeSettings();

            var nudge = engine.EvaluateProactiveNudges(
                currentMode: ActivityMode.Work,
                targetMode: ActivityMode.Work,
                activeProcess: "code.exe",
                activeTitle: "VS Code",
                elapsedSeconds: 600,
                workLimitSec: 1500,
                batteryCap: 10.0, // Critical (<15%)
                isFlowSession: false,
                idleSecVal: 0,
                settings: settings,
                contextSwitchTimestamps: Array.Empty<double>(),
                currentTimestampSec: 1000.0);

            Assert.NotNull(nudge);
            Assert.Equal(NudgeSeverity.Critical, nudge.Severity);
            Assert.Contains("Critical Stamina Depleted", nudge.Title);
        }

        [Fact]
        public void CognitiveNudgeEngine_FlowShield_SuppressesNonCriticalNudges()
        {
            var engine = new CognitiveNudgeEngine();
            var settings = new NudgeSettings();

            // Sprint limit exceeded (Priority 2), but Flow Shield active
            var nudge = engine.EvaluateProactiveNudges(
                currentMode: ActivityMode.Work,
                targetMode: ActivityMode.Work,
                activeProcess: "code.exe",
                activeTitle: "VS Code",
                elapsedSeconds: 1600,
                workLimitSec: 1500,
                batteryCap: 80.0, // Healthy battery
                isFlowSession: true, // Flow active!
                idleSecVal: 0,
                settings: settings,
                contextSwitchTimestamps: Array.Empty<double>(),
                currentTimestampSec: 1000.0);

            Assert.Null(nudge);
        }

        [Fact]
        public void CognitiveNudgeEngine_DistractionDwell_RequiresGracePeriod()
        {
            var engine = new CognitiveNudgeEngine();
            var settings = new NudgeSettings { ProactivityLevel = "balanced" }; // 30s dwell

            // Tick 1 at t=100s: drift starts
            var nudge1 = engine.EvaluateProactiveNudges(
                currentMode: ActivityMode.Work,
                targetMode: ActivityMode.Recharge,
                activeProcess: "steam.exe",
                activeTitle: "Steam",
                elapsedSeconds: 500,
                workLimitSec: 1500,
                batteryCap: 80.0,
                isFlowSession: false,
                idleSecVal: 0,
                settings: settings,
                contextSwitchTimestamps: Array.Empty<double>(),
                currentTimestampSec: 100.0);

            Assert.Null(nudge1); // Dwell grace period active

            // Tick 2 at t=131s: dwell exceeded (>30s)
            var nudge2 = engine.EvaluateProactiveNudges(
                currentMode: ActivityMode.Work,
                targetMode: ActivityMode.Recharge,
                activeProcess: "steam.exe",
                activeTitle: "Steam",
                elapsedSeconds: 531,
                workLimitSec: 1500,
                batteryCap: 80.0,
                isFlowSession: false,
                idleSecVal: 0,
                settings: settings,
                contextSwitchTimestamps: Array.Empty<double>(),
                currentTimestampSec: 131.0);

            Assert.NotNull(nudge2);
            Assert.Equal(NudgeSeverity.Warning, nudge2.Severity);
            Assert.Contains("Distraction Drift", nudge2.Title);
        }

        [Fact]
        public void CognitiveNudgeEngine_Snooze_SuppressesNonCriticalAlerts()
        {
            var engine = new CognitiveNudgeEngine();
            var settings = new NudgeSettings();

            engine.SnoozeUntilSec = 2000.0; // Snoozed until t=2000

            var nudge = engine.EvaluateProactiveNudges(
                currentMode: ActivityMode.Work,
                targetMode: ActivityMode.Work,
                activeProcess: "code.exe",
                activeTitle: "VS Code",
                elapsedSeconds: 1600,
                workLimitSec: 1500,
                batteryCap: 80.0,
                isFlowSession: false,
                idleSecVal: 0,
                settings: settings,
                contextSwitchTimestamps: Array.Empty<double>(),
                currentTimestampSec: 1000.0);

            Assert.Null(nudge);
        }
    }
}
