/*
Unit tests validating CalendarSyncEngine SSRF protection, iCal RFC-5545 parsing, and persistence.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.IO;
using System.Threading.Tasks;
using Xunit;
using MindFlow.Core.Calendar;
using MindFlow.Data.Database;

namespace MindFlow.Tests
{
    public class CalendarSyncTests : IDisposable
    {
        private readonly string _dbPath;

        public CalendarSyncTests()
        {
            _dbPath = Path.Combine(Path.GetTempPath(), "mindflow_cal_test_" + Guid.NewGuid().ToString("N") + ".db");
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
        public void CalendarSync_IsSafeUrl_BlocksSsrfTargets()
        {
            // Invalid schemes
            Assert.False(CalendarSyncEngine.IsSafeUrl("file:///etc/passwd"));
            Assert.False(CalendarSyncEngine.IsSafeUrl("ftp://127.0.0.1/test"));
            Assert.False(CalendarSyncEngine.IsSafeUrl("gopher://localhost:70"));
            Assert.False(CalendarSyncEngine.IsSafeUrl(""));
            Assert.False(CalendarSyncEngine.IsSafeUrl("not_a_url"));

            // Loopbacks
            Assert.False(CalendarSyncEngine.IsSafeUrl("http://127.0.0.1/cal.ics"));
            Assert.False(CalendarSyncEngine.IsSafeUrl("http://localhost/cal.ics"));
            Assert.False(CalendarSyncEngine.IsSafeUrl("http://[::1]/cal.ics"));

            // Private RFC-1918
            Assert.False(CalendarSyncEngine.IsSafeUrl("http://10.0.0.1/test.ics"));
            Assert.False(CalendarSyncEngine.IsSafeUrl("http://192.168.1.1/cal.ics"));
            Assert.False(CalendarSyncEngine.IsSafeUrl("http://172.16.0.1/cal.ics"));

            // Link-local / AWS Metadata
            Assert.False(CalendarSyncEngine.IsSafeUrl("http://169.254.169.254/latest/meta-data/"));
        }

        [Fact]
        public void CalendarSync_ParseIcsContent_ExtractsVEventDetails()
        {
            string ics = @"BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//EN
BEGIN:VEVENT
UID:uid-sprint-123@example.com
DTSTART:20260816T140000Z
DTEND:20260816T150000Z
SUMMARY:Deep Focus Sprint
DESCRIPTION:Work on native core engine
END:VEVENT
END:VCALENDAR";

            var events = CalendarSyncEngine.ParseIcsContent(ics);

            Assert.Single(events);
            var ev = events[0];
            Assert.Equal("Deep Focus Sprint", ev.Title);
            Assert.Equal("Work on native core engine", ev.Description);
            Assert.Equal("uid-sprint-123@example.com", ev.Uid);
            Assert.Equal(new DateTime(2026, 8, 16, 14, 0, 0, DateTimeKind.Utc), ev.StartTime);
            Assert.Equal(new DateTime(2026, 8, 16, 15, 0, 0, DateTimeKind.Utc), ev.EndTime);
        }

        [Fact]
        public async Task CalendarSync_Database_SavesAndRetrievesEvents()
        {
            using var db = new MindFlowDb(_dbPath);

            var events = new[]
            {
                ("Morning Planning", "2026-10-07T09:00:00Z", "2026-10-07T09:30:00Z"),
                ("Deep Coding Sprint", "2026-10-07T10:00:00Z", "2026-10-07T12:00:00Z")
            };

            await db.SaveCalendarEventsAsync(events);
            await db.FlushAsync();

            var loaded = await db.GetCalendarEventsAsync("2026-10-07");
            Assert.Equal(2, loaded.Count);
            Assert.Contains(loaded, e => e.Title == "Morning Planning");
            Assert.Contains(loaded, e => e.Title == "Deep Coding Sprint");
        }
    }
}
