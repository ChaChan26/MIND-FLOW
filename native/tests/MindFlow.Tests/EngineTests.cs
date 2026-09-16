/*
Unit tests validating cognitive battery mathematics, task classification, mode transitions, and CRDTs.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using Xunit;
using MindFlow.Core.Battery;
using MindFlow.Core.Classification;
using MindFlow.Core.State;
using MindFlow.Core.Sync;

namespace MindFlow.Tests
{
    public class EngineTests
    {
        [Fact]
        public void CognitiveBattery_WorkDrain_AppliesFatigueAndSwitchPenalty()
        {
            var battery = new CognitiveBattery(initialCapacity: 100.0, initialConsecutiveWork: 0.0);
            
            // 10 minutes of work with 2 context switches/min
            var (capacity, consecutiveWork) = battery.ProcessTick(ActivityMode.Work, elapsedMinutes: 10.0, contextSwitchesPerMin: 2.0);

            Assert.Equal(10.0, consecutiveWork);
            Assert.True(capacity < 100.0);
            
            // Expected drain calculation:
            // penalty = 1.0 + (10.0 * 0.035) = 1.35
            // switchPenalty = 1.0 + (0.15 * 2.0) = 1.30
            // drain = 0.5 * 1.35 * 1.30 * 10.0 = 8.775
            // capacity = 100.0 - 8.775 = 91.225
            Assert.Equal(91.225, capacity, precision: 3);
        }

        [Fact]
        public void CognitiveBattery_RestRecovery_RestoresCapacity()
        {
            var battery = new CognitiveBattery(initialCapacity: 80.0, initialConsecutiveWork: 30.0);

            // 4 minutes of rest
            var (capacity, consecutiveWork) = battery.ProcessTick(ActivityMode.Rest, elapsedMinutes: 4.0);

            // recovery = 2.5 * 4.0 = 10.0 -> capacity = 90.0
            Assert.Equal(90.0, capacity, precision: 3);
            
            // decay = 3.0 * 4.0 = 12.0 -> consecutiveWork = 30.0 - 12.0 = 18.0
            Assert.Equal(18.0, consecutiveWork, precision: 3);
        }

        [Fact]
        public void CognitiveBattery_NeutralMode_PreservesValues()
        {
            var battery = new CognitiveBattery(initialCapacity: 75.0, initialConsecutiveWork: 20.0);
            var (capacity, consecutiveWork) = battery.ProcessTick(ActivityMode.Neutral, elapsedMinutes: 15.0);

            Assert.Equal(75.0, capacity);
            Assert.Equal(20.0, consecutiveWork);
        }

        [Fact]
        public void TaskClassifier_CorrectlyIdentifiesWorkAndRecharge()
        {
            var classifier = new TaskClassifier();

            Assert.Equal(ActivityMode.Work, classifier.Classify("devenv.exe", "MindFlow - Microsoft Visual Studio"));
            Assert.Equal(ActivityMode.Work, classifier.Classify("Code.exe", "app.py - Visual Studio Code"));
            Assert.Equal(ActivityMode.Recharge, classifier.Classify("chrome.exe", "YouTube - Calm Ambient Music"));
            Assert.Equal(ActivityMode.Neutral, classifier.Classify("explorer.exe", "File Explorer"));
        }

        [Fact]
        public void TaskClassifier_RejectsUnsafeRegex()
        {
            Assert.False(TaskClassifier.IsSafeRegex(@"(a+)+"));
            Assert.False(TaskClassifier.IsSafeRegex(@"(\w*)*"));
            Assert.True(TaskClassifier.IsSafeRegex(@"vscode|code\.exe"));
        }

        [Fact]
        public void ModeEngine_ManualOverride_PreventsAutomaticSwitch()
        {
            var engine = new ModeEngine(ActivityMode.Work);
            engine.SetManualMode(ActivityMode.Work, overrideDurationSeconds: 120);

            // User switches to YouTube, but manual override is active
            engine.EvaluateTick(classifiedMode: ActivityMode.Recharge, idleSeconds: 0.0, deltaSeconds: 5.0);

            Assert.Equal(ActivityMode.Work, engine.CurrentMode);
        }

        [Fact]
        public void ModeEngine_IdleTimeout_TransitionsToRest()
        {
            var engine = new ModeEngine(ActivityMode.Work)
            {
                IdleTimeoutSeconds = 60.0
            };

            engine.EvaluateTick(classifiedMode: ActivityMode.Work, idleSeconds: 65.0, deltaSeconds: 1.0);

            Assert.Equal(ActivityMode.Rest, engine.CurrentMode);
        }

        [Fact]
        public void ModeEngine_ManualOverride_PreemptsIdleTimeout()
        {
            var engine = new ModeEngine(ActivityMode.Work)
            {
                IdleTimeoutSeconds = 60.0
            };
            engine.SetManualMode(ActivityMode.Work, overrideDurationSeconds: 120);

            // Even with idleSeconds exceeding timeout, user manual focus sprint is preserved
            engine.EvaluateTick(classifiedMode: ActivityMode.Work, idleSeconds: 90.0, deltaSeconds: 1.0);

            Assert.Equal(ActivityMode.Work, engine.CurrentMode);
        }

        [Fact]
        public void HLC_OrdersDeterministically()
        {
            var clockA = new HybridLogicalClock("nodeA");
            var clockB = new HybridLogicalClock("nodeB");

            var t1 = clockA.Now();
            var t2 = clockA.Now();

            Assert.True(t2.CompareTo(t1) > 0);

            var tRemote = clockB.Update(t2);
            Assert.True(tRemote.CompareTo(t2) > 0);
        }
    }
}
