/*
Unit tests validating Win32 WinEventTracker lifecycle, clean STA termination, and safe query handling.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Diagnostics;
using MindFlow.Win32.Hooks;
using Xunit;

namespace MindFlow.Tests
{
    public class WinEventTrackerTests
    {
        [Fact]
        public void WinEventTracker_ZeroHwnd_ReturnsNullDetails()
        {
            var details = WinEventTracker.QueryWindowDetails(IntPtr.Zero);
            Assert.Null(details);
        }

        [Fact]
        public void WinEventTracker_StartAndDispose_TerminatesCleanlyWithoutHanging()
        {
            var tracker = new WinEventTracker();
            tracker.Start();

            var sw = Stopwatch.StartNew();
            tracker.Dispose();
            sw.Stop();

            // Must terminate cleanly via WM_QUIT within timeout, proving no STA hang
            Assert.True(sw.ElapsedMilliseconds < 3000, $"Dispose took too long: {sw.ElapsedMilliseconds}ms");
        }
    }
}
