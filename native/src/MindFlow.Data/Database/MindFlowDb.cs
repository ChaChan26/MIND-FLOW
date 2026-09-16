/*
Thread-safe SQLite WAL persistence engine with serialized write queue and exponential retry backoff.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Channels;
using System.Threading.Tasks;
using Microsoft.Data.Sqlite;
using MindFlow.Data.Models;

namespace MindFlow.Data.Database
{
    public class MindFlowDb : IDisposable
    {
        private readonly string _dbPath;
        private readonly string _connectionString;
        private readonly Channel<Func<SqliteConnection, Task>> _writeChannel;
        private readonly CancellationTokenSource _cts = new();
        private readonly Task _writeWorkerTask;

        public MindFlowDb(string? dbPath = null)
        {
            if (string.IsNullOrWhiteSpace(dbPath))
            {
                string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
                string mindDir = Path.Combine(appData, "MIND");
                Directory.CreateDirectory(mindDir);
                _dbPath = Path.Combine(mindDir, "mind_flow_data.db");
            }
            else
            {
                _dbPath = dbPath;
                string? dir = Path.GetDirectoryName(_dbPath);
                if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            }

            _connectionString = $"Data Source={_dbPath};Mode=ReadWriteCreate;";
            _writeChannel = Channel.CreateBounded<Func<SqliteConnection, Task>>(new BoundedChannelOptions(1000)
            {
                FullMode = BoundedChannelFullMode.Wait
            });

            InitializeSchema();
            _writeWorkerTask = Task.Run(ProcessWriteQueueAsync);
        }

        private void InitializeSchema()
        {
            using var conn = new SqliteConnection(_connectionString);
            conn.Open();

            using var cmd = conn.CreateCommand();
            cmd.CommandText = @"
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=NORMAL;

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS battery_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    current_capacity REAL NOT NULL DEFAULT 100.0,
                    consecutive_work_minutes REAL NOT NULL DEFAULT 0.0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT,
                    start TEXT,
                    end TEXT,
                    duration REAL,
                    brain_dump TEXT,
                    bypassed INTEGER DEFAULT 0,
                    is_flow INTEGER DEFAULT 0,
                    flow_duration REAL DEFAULT 0.0
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start);

                CREATE TABLE IF NOT EXISTS app_usage (
                    date TEXT,
                    process TEXT,
                    title TEXT,
                    titles TEXT,
                    duration REAL,
                    PRIMARY KEY (date, process)
                );
                CREATE INDEX IF NOT EXISTS idx_app_usage_date ON app_usage(date);

                CREATE TABLE IF NOT EXISTS context_switches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    from_process TEXT,
                    to_process TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_context_switches_ts ON context_switches(timestamp);

                CREATE TABLE IF NOT EXISTS reflections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    energy_level INTEGER,
                    friction_level INTEGER,
                    summary TEXT,
                    mood TEXT,
                    sleep_hours REAL,
                    sleep_quality INTEGER
                );

                CREATE TABLE IF NOT EXISTS achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    description TEXT,
                    awarded_at TEXT
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT,
                    completed INTEGER DEFAULT 0,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS focus_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    duration_minutes INTEGER,
                    task_label TEXT,
                    completed INTEGER,
                    stamina_start REAL,
                    stamina_end REAL
                );
                CREATE INDEX IF NOT EXISTS idx_focus_sessions_ts ON focus_sessions(timestamp);

                CREATE TABLE IF NOT EXISTS gratitude_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE,
                    entry_1 TEXT,
                    entry_2 TEXT,
                    entry_3 TEXT
                );

                CREATE TABLE IF NOT EXISTS calendar_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    start_time TEXT,
                    end_time TEXT
                );

                CREATE TABLE IF NOT EXISTS hydration (date TEXT PRIMARY KEY, cups REAL);
                CREATE TABLE IF NOT EXISTS steps (date TEXT PRIMARY KEY, count INTEGER);
                CREATE TABLE IF NOT EXISTS sleep (date TEXT PRIMARY KEY, hours REAL, quality INTEGER);

                INSERT OR IGNORE INTO battery_state (id, current_capacity, consecutive_work_minutes)
                VALUES (1, 100.0, 0.0);
            ";
            cmd.ExecuteNonQuery();
        }

        private async Task ProcessWriteQueueAsync()
        {
            using var conn = new SqliteConnection(_connectionString);
            await conn.OpenAsync(_cts.Token);

            var reader = _writeChannel.Reader;
            while (await reader.WaitToReadAsync(_cts.Token))
            {
                while (reader.TryRead(out var writeOp))
                {
                    int retries = 3;
                    int delayMs = 25;

                    while (retries > 0)
                    {
                        try
                        {
                            await writeOp(conn);
                            break;
                        }
                        catch (SqliteException ex) when (ex.SqliteErrorCode == 5 /* SQLITE_BUSY */ || ex.SqliteErrorCode == 6 /* SQLITE_LOCKED */)
                        {
                            retries--;
                            if (retries == 0)
                                break;

                            await Task.Delay(delayMs, _cts.Token);
                            delayMs *= 2;
                        }
                        catch
                        {
                            break;
                        }
                    }
                }
            }
        }

        public Task QueueWriteAsync(Func<SqliteConnection, Task> operation)
        {
            return _writeChannel.Writer.WriteAsync(operation, _cts.Token).AsTask();
        }

        public async Task SaveBatteryStateAsync(double capacity, double consecutiveWorkMinutes)
        {
            await QueueWriteAsync(async conn =>
            {
                using var cmd = conn.CreateCommand();
                cmd.CommandText = @"
                    INSERT INTO battery_state (id, current_capacity, consecutive_work_minutes, last_updated)
                    VALUES (1, @cap, @work, datetime('now'))
                    ON CONFLICT(id) DO UPDATE SET
                        current_capacity = excluded.current_capacity,
                        consecutive_work_minutes = excluded.consecutive_work_minutes,
                        last_updated = datetime('now');
                ";
                cmd.Parameters.AddWithValue("@cap", capacity);
                cmd.Parameters.AddWithValue("@work", consecutiveWorkMinutes);
                await cmd.ExecuteNonQueryAsync();
            });
        }

        public async Task<BatteryStateRecord> GetBatteryStateAsync()
        {
            using var conn = new SqliteConnection(_connectionString);
            await conn.OpenAsync();

            using var cmd = conn.CreateCommand();
            cmd.CommandText = "SELECT current_capacity, consecutive_work_minutes, last_updated FROM battery_state WHERE id = 1;";
            using var reader = await cmd.ExecuteReaderAsync();

            if (await reader.ReadAsync())
            {
                return new BatteryStateRecord
                {
                    Capacity = reader.GetDouble(0),
                    ConsecutiveWorkMinutes = reader.GetDouble(1),
                    LastUpdated = reader.IsDBNull(2) ? DateTime.UtcNow : DateTime.Parse(reader.GetString(2))
                };
            }

            return new BatteryStateRecord();
        }

        public async Task LogSessionAsync(string mode, DateTime start, DateTime end, double durationSeconds, bool isFlow = false)
        {
            await QueueWriteAsync(async conn =>
            {
                using var cmd = conn.CreateCommand();
                cmd.CommandText = @"
                    INSERT INTO sessions (mode, start, end, duration, is_flow, flow_duration)
                    VALUES (@mode, @start, @end, @duration, @is_flow, @flow_dur);
                ";
                cmd.Parameters.AddWithValue("@mode", mode);
                cmd.Parameters.AddWithValue("@start", start.ToString("o"));
                cmd.Parameters.AddWithValue("@end", end.ToString("o"));
                cmd.Parameters.AddWithValue("@duration", durationSeconds);
                cmd.Parameters.AddWithValue("@is_flow", isFlow ? 1 : 0);
                cmd.Parameters.AddWithValue("@flow_dur", isFlow ? durationSeconds : 0.0);
                await cmd.ExecuteNonQueryAsync();
            });
        }

        public async Task LogAppUsageAsync(string process, string title, double durationSeconds)
        {
            string today = DateTime.UtcNow.ToString("yyyy-MM-dd");
            await QueueWriteAsync(async conn =>
            {
                using var cmd = conn.CreateCommand();
                cmd.CommandText = @"
                    INSERT INTO app_usage (date, process, title, duration)
                    VALUES (@date, @proc, @title, @dur)
                    ON CONFLICT(date, process) DO UPDATE SET
                        duration = duration + excluded.duration,
                        title = excluded.title;
                ";
                cmd.Parameters.AddWithValue("@date", today);
                cmd.Parameters.AddWithValue("@proc", process);
                cmd.Parameters.AddWithValue("@title", title);
                cmd.Parameters.AddWithValue("@dur", durationSeconds);
                await cmd.ExecuteNonQueryAsync();
            });
        }

        public async Task<List<AppUsageRecord>> GetTodayAppUsageAsync()
        {
            var results = new List<AppUsageRecord>();
            string today = DateTime.UtcNow.ToString("yyyy-MM-dd");

            using var conn = new SqliteConnection(_connectionString);
            await conn.OpenAsync();

            using var cmd = conn.CreateCommand();
            cmd.CommandText = "SELECT date, process, title, duration FROM app_usage WHERE date = @today ORDER BY duration DESC LIMIT 15;";
            cmd.Parameters.AddWithValue("@today", today);

            using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                results.Add(new AppUsageRecord
                {
                    Date = reader.GetString(0),
                    Process = reader.GetString(1),
                    Title = reader.IsDBNull(2) ? "" : reader.GetString(2),
                    Duration = reader.GetDouble(3)
                });
            }

            return results;
        }

        public async Task SetSettingAsync(string key, string value)
        {
            await QueueWriteAsync(async conn =>
            {
                using var cmd = conn.CreateCommand();
                cmd.CommandText = "INSERT OR REPLACE INTO settings (key, value) VALUES (@key, @val);";
                cmd.Parameters.AddWithValue("@key", key);
                cmd.Parameters.AddWithValue("@val", value);
                await cmd.ExecuteNonQueryAsync();
            });
        }

        public async Task<string?> GetSettingAsync(string key)
        {
            using var conn = new SqliteConnection(_connectionString);
            await conn.OpenAsync();

            using var cmd = conn.CreateCommand();
            cmd.CommandText = "SELECT value FROM settings WHERE key = @key;";
            cmd.Parameters.AddWithValue("@key", key);
            var result = await cmd.ExecuteScalarAsync();
            return result?.ToString();
        }

        public async Task LogContextSwitchAsync(string fromProcess, string toProcess, DateTime? timestamp = null)
        {
            DateTime ts = timestamp ?? DateTime.UtcNow;
            await QueueWriteAsync(async conn =>
            {
                using var cmd = conn.CreateCommand();
                cmd.CommandText = @"
                    INSERT INTO context_switches (timestamp, from_process, to_process)
                    VALUES (@ts, @from, @to);
                ";
                cmd.Parameters.AddWithValue("@ts", ts.ToString("o"));
                cmd.Parameters.AddWithValue("@from", fromProcess);
                cmd.Parameters.AddWithValue("@to", toProcess);
                await cmd.ExecuteNonQueryAsync();
            });
        }

        public async Task<int> GetTodayContextSwitchCountAsync()
        {
            string today = DateTime.UtcNow.ToString("yyyy-MM-dd");
            using var conn = new SqliteConnection(_connectionString);
            await conn.OpenAsync();

            using var cmd = conn.CreateCommand();
            cmd.CommandText = "SELECT COUNT(*) FROM context_switches WHERE DATE(timestamp) = @today;";
            cmd.Parameters.AddWithValue("@today", today);
            var result = await cmd.ExecuteScalarAsync();
            return result != null && result != DBNull.Value ? Convert.ToInt32(result) : 0;
        }

        public async Task<List<HourlyProductivityRecord>> GetTodayHourlyProductivityAsync()
        {
            var results = new List<HourlyProductivityRecord>();
            string today = DateTime.UtcNow.ToString("yyyy-MM-dd");

            using var conn = new SqliteConnection(_connectionString);
            await conn.OpenAsync();

            using var cmd = conn.CreateCommand();
            cmd.CommandText = @"
                SELECT 
                    CAST(strftime('%H', start) AS INTEGER) AS hour_val,
                    ROUND(SUM(CASE WHEN LOWER(mode) = 'work' THEN duration ELSE 0 END) / 60.0, 1) AS work_mins,
                    ROUND(SUM(CASE WHEN LOWER(mode) IN ('recharge', 'rest') THEN duration ELSE 0 END) / 60.0, 1) AS recharge_mins,
                    ROUND(SUM(flow_duration) / 60.0, 1) AS flow_mins
                FROM sessions
                WHERE DATE(start) = @today
                GROUP BY hour_val
                ORDER BY hour_val ASC;
            ";
            cmd.Parameters.AddWithValue("@today", today);

            using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                results.Add(new HourlyProductivityRecord
                {
                    Hour = reader.GetInt32(0),
                    WorkMinutes = reader.GetDouble(1),
                    RechargeMinutes = reader.GetDouble(2),
                    FlowMinutes = reader.GetDouble(3)
                });
            }

            return results;
        }

        public async Task LogFocusSessionAsync(int durationMinutes, string taskLabel = "Focus Sprint", bool completed = true, double staminaStart = 100.0, double staminaEnd = 100.0, DateTime? timestamp = null)
        {
            DateTime ts = timestamp ?? DateTime.UtcNow;
            await QueueWriteAsync(async conn =>
            {
                using var cmd = conn.CreateCommand();
                cmd.CommandText = @"
                    INSERT INTO focus_sessions (timestamp, duration_minutes, task_label, completed, stamina_start, stamina_end)
                    VALUES (@ts, @dur, @task, @comp, @start, @end);
                ";
                cmd.Parameters.AddWithValue("@ts", ts.ToString("o"));
                cmd.Parameters.AddWithValue("@dur", durationMinutes);
                cmd.Parameters.AddWithValue("@task", taskLabel);
                cmd.Parameters.AddWithValue("@comp", completed ? 1 : 0);
                cmd.Parameters.AddWithValue("@start", staminaStart);
                cmd.Parameters.AddWithValue("@end", staminaEnd);
                await cmd.ExecuteNonQueryAsync();
            });
        }

        public async Task<List<FocusSessionRecord>> GetTodayFocusSessionsAsync()
        {
            var results = new List<FocusSessionRecord>();
            string today = DateTime.UtcNow.ToString("yyyy-MM-dd");

            using var conn = new SqliteConnection(_connectionString);
            await conn.OpenAsync();

            using var cmd = conn.CreateCommand();
            cmd.CommandText = @"
                SELECT id, timestamp, duration_minutes, task_label, completed, stamina_start, stamina_end
                FROM focus_sessions
                WHERE DATE(timestamp) = @today
                ORDER BY timestamp DESC;
            ";
            cmd.Parameters.AddWithValue("@today", today);

            using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                results.Add(new FocusSessionRecord
                {
                    Id = reader.GetInt64(0),
                    Timestamp = reader.GetString(1),
                    DurationMinutes = reader.GetInt32(2),
                    TaskLabel = reader.IsDBNull(3) ? "Focus Sprint" : reader.GetString(3),
                    Completed = reader.GetInt32(4),
                    StaminaStart = reader.IsDBNull(5) ? 100.0 : reader.GetDouble(5),
                    StaminaEnd = reader.IsDBNull(6) ? 100.0 : reader.GetDouble(6)
                });
            }

            return results;
        }

        public async Task<int> GetTodayFocusMinutesAsync()
        {
            string today = DateTime.UtcNow.ToString("yyyy-MM-dd");
            using var conn = new SqliteConnection(_connectionString);
            await conn.OpenAsync();

            using var cmd = conn.CreateCommand();
            cmd.CommandText = "SELECT COALESCE(SUM(duration_minutes), 0) FROM focus_sessions WHERE DATE(timestamp) = @today AND completed = 1;";
            cmd.Parameters.AddWithValue("@today", today);
            var result = await cmd.ExecuteScalarAsync();
            return result != null && result != DBNull.Value ? Convert.ToInt32(result) : 0;
        }

        public async Task FlushAsync()
        {
            var tcs = new TaskCompletionSource<bool>();
            await _writeChannel.Writer.WriteAsync(conn =>
            {
                tcs.SetResult(true);
                return Task.CompletedTask;
            }, _cts.Token);
            await tcs.Task;
        }

        public void Dispose()
        {
            _cts.Cancel();
            _writeChannel.Writer.Complete();
            try { _writeWorkerTask.Wait(1000); } catch { }
            _cts.Dispose();
        }
    }
}
