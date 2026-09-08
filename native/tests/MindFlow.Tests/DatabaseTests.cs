/*
Unit and integration tests validating SQLite WAL persistence, asynchronous write queue, and analytics queries.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.IO;
using System.Threading.Tasks;
using Microsoft.Data.Sqlite;
using MindFlow.Data.Database;
using Xunit;

namespace MindFlow.Tests
{
    public class DatabaseTests : IDisposable
    {
        private readonly string _tempDbPath;
        private readonly MindFlowDb _db;

        public DatabaseTests()
        {
            _tempDbPath = Path.Combine(Path.GetTempPath(), $"mindflow_test_{Guid.NewGuid():N}.db");
            _db = new MindFlowDb(_tempDbPath);
        }

        public void Dispose()
        {
            _db.Dispose();
            try
            {
                if (File.Exists(_tempDbPath)) File.Delete(_tempDbPath);
                string wal = $"{_tempDbPath}-wal";
                if (File.Exists(wal)) File.Delete(wal);
                string shm = $"{_tempDbPath}-shm";
                if (File.Exists(shm)) File.Delete(shm);
            }
            catch
            {
                // Ignore cleanup errors on locked OS handles
            }
        }

        [Fact]
        public async Task Database_Initialization_EnablesWALMode()
        {
            using var conn = new SqliteConnection($"Data Source={_tempDbPath};");
            await conn.OpenAsync();

            using var cmd = conn.CreateCommand();
            cmd.CommandText = "PRAGMA journal_mode;";
            var mode = await cmd.ExecuteScalarAsync();

            Assert.NotNull(mode);
            Assert.Equal("wal", mode.ToString()?.ToLowerInvariant());
        }

        [Fact]
        public async Task Database_BatteryState_SavesAndRetrieves()
        {
            await _db.SaveBatteryStateAsync(84.5, 27.0);
            await _db.FlushAsync();

            var state = await _db.GetBatteryStateAsync();

            Assert.Equal(84.5, state.Capacity, precision: 1);
            Assert.Equal(27.0, state.ConsecutiveWorkMinutes, precision: 1);
        }

        [Fact]
        public async Task Database_ContextSwitch_LogsAndCountsToday()
        {
            int initialCount = await _db.GetTodayContextSwitchCountAsync();
            Assert.Equal(0, initialCount);

            await _db.LogContextSwitchAsync("devenv.exe", "chrome.exe");
            await _db.LogContextSwitchAsync("chrome.exe", "slack.exe");
            await _db.FlushAsync();

            int updatedCount = await _db.GetTodayContextSwitchCountAsync();
            Assert.Equal(2, updatedCount);
        }

        [Fact]
        public async Task Database_HourlyProductivity_AggregatesAccurately()
        {
            DateTime now = DateTime.UtcNow;
            DateTime session1Start = new DateTime(now.Year, now.Month, now.Day, 10, 0, 0, DateTimeKind.Utc);
            DateTime session1End = session1Start.AddMinutes(25);

            DateTime session2Start = new DateTime(now.Year, now.Month, now.Day, 10, 30, 0, DateTimeKind.Utc);
            DateTime session2End = session2Start.AddMinutes(5);

            // 25 mins work in hour 10 (with 25 mins flow)
            await _db.LogSessionAsync("Work", session1Start, session1End, 1500.0, isFlow: true);
            // 5 mins break in hour 10
            await _db.LogSessionAsync("Rest", session2Start, session2End, 300.0, isFlow: false);
            await _db.FlushAsync();

            var hourly = await _db.GetTodayHourlyProductivityAsync();

            var record = hourly.Find(h => h.Hour == 10);
            Assert.NotNull(record);
            Assert.Equal(25.0, record.WorkMinutes, precision: 1);
            Assert.Equal(5.0, record.RechargeMinutes, precision: 1);
            Assert.Equal(25.0, record.FlowMinutes, precision: 1);
        }
    }
}
