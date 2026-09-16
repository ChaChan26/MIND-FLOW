/*
Active window and process metadata model.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;

namespace MindFlow.Win32.Hooks
{
    public class WindowDetails
    {
        public IntPtr Hwnd { get; }
        public string Title { get; }
        public string ProcessName { get; }
        public string ExePath { get; }
        public uint ProcessId { get; }
        public DateTime Timestamp { get; }

        public WindowDetails(IntPtr hwnd, string title, string processName, string exePath, uint processId)
        {
            Hwnd = hwnd;
            Title = title ?? string.Empty;
            ProcessName = processName ?? string.Empty;
            ExePath = exePath ?? string.Empty;
            ProcessId = processId;
            Timestamp = DateTime.UtcNow;
        }

        public override string ToString() => $"[{ProcessName}] {Title} (PID: {ProcessId})";
    }
}
