/*
Unit tests validating MindFlowDb analytics queries and CRDT LWW-Element-Set with tombstone GC.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Xunit;
using MindFlow.Core.Sync;
using MindFlow.Data.Database;

namespace MindFlow.Tests
{
    public class AnalyticsAndCrdtTests : IDisposable
    {
        private readonly string _dbPath;

        public AnalyticsAndCrdtTests()
        {
            _dbPath = Path.Combine(Path.GetTempPath(), "mindflow_analytics_test_" + Guid.NewGuid().ToString("N") + ".db");
        }

        public void Dispose()
        {
            try
            {
                if (File.Exists(_dbPath)) File.Delete(_dbPath);
            }
            catch { }
        }

        [Fact]
        public async Task MindFlowDb_Analytics_AggregatesTrendsAndFatigue()
        {
            using var db = new MindFlowDb(_dbPath);

            DateTime now = DateTime.UtcNow;

            // Log a 3000s work session (continuous work over 45m threshold)
            await db.LogSessionAsync("Work", now.AddHours(-3), now.AddHours(-2), durationSeconds: 3000, isFlow: true);
            // Log a 600s rest session
            await db.LogSessionAsync("Rest", now.AddHours(-2), now.AddHours(-1.8), durationSeconds: 600, isFlow: false);

            await db.FlushAsync();

            var trends = await db.GetDailyProductivityTrendsAsync(days: 7);
            Assert.NotEmpty(trends);
            var todayTrend = trends.Last();
            Assert.True(todayTrend.WorkMinutes >= 50.0);
            Assert.True(todayTrend.RestMinutes >= 10.0);

            var fatigue = await db.GetFatigueDurationAnalyticsAsync(days: 30);
            Assert.Equal(3000.0, fatigue.TotalWorkSeconds);
            Assert.Equal(600.0, fatigue.TotalRestSeconds);
            Assert.Equal(3000.0, fatigue.LongestContinuousWorkSeconds);
            Assert.True(fatigue.FatigueRiskScore > 0);
        }

        [Fact]
        public void Crdt_LWWElementSet_AddRemoveAndMerge_RespectsLWW()
        {
            var hlc = new HybridLogicalClock("node-1");

            var setA = new LWWElementSet<string>();
            var setB = new LWWElementSet<string>();

            var t1 = hlc.Now();
            setA.Add("rule-1", t1);

            var t2 = hlc.Now();
            setB.Remove("rule-1", t2); // Removed later at t2

            setA.Merge(setB);
            var elements = setA.ReadElements();

            Assert.DoesNotContain("rule-1", elements);
        }

        [Fact]
        public void Crdt_LWWElementSet_GarbageCollectTombstones_PurgesExpired()
        {
            var hlc = new HybridLogicalClock("node-1");
            var set = new LWWElementSet<string>();

            // Old timestamp (2 days ago)
            long twoDaysAgoMs = DateTimeOffset.UtcNow.AddDays(-2).ToUnixTimeMilliseconds();
            var oldTs = new HLCTimestamp(twoDaysAgoMs, 0, "node-1");

            set.Add("expired-rule", oldTs);
            set.Remove("expired-rule", oldTs);

            // GC tombstones older than 24 hours (86,400,000 ms)
            int purged = set.GarbageCollectTombstones(maxAgeMs: 86400000);

            Assert.Equal(1, purged);
            Assert.Empty(set.ReadElements());
        }

        [Fact]
        public void CrdtSyncEngine_Merge_SynchronizesAllRegistersAndCounters()
        {
            var engineA = new CrdtSyncEngine("client-A");
            var engineB = new CrdtSyncEngine("client-B");

            var tA = engineA.Hlc.Now();
            engineA.StaminaBattery.Set(75.0, tA);
            engineA.CategoryRules.Add("custom-rule-1", tA);

            var counterB = engineB.Counters.GetOrAdd("switches", _ => new PNCounter());
            counterB.Increment(engineB.ClientId, 5);

            engineA.Merge(engineB);

            Assert.Equal(75.0, engineA.StaminaBattery.Value);
            Assert.Contains("custom-rule-1", engineA.CategoryRules.ReadElements());
            Assert.Equal(5, engineA.Counters["switches"].Value);
        }
    }
}
