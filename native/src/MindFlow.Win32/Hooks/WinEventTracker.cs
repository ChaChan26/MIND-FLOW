/*
Event-driven active window listener utilizing WinEventHook on a dedicated STA thread.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace MindFlow.Win32.Hooks
{
    public class WinEventTracker : IDisposable
    {
        private const uint EVENT_SYSTEM_FOREGROUND = 0x0003;
        private const uint EVENT_OBJECT_NAMECHANGE = 0x800C;
        private const uint WINEVENT_OUTOFCONTEXT = 0x0000;
        private const uint WINEVENT_SKIPOWNPROCESS = 0x0002;
        private const uint GA_ROOT = 2;
        private const uint WM_QUIT = 0x0012;

        private delegate void WinEventDelegate(
            IntPtr hWinEventHook, uint eventType, IntPtr hwnd, int idObject, int idChild,
            uint dwEventThread, uint dwmsEventTime);

        [DllImport("user32.dll")]
        private static extern IntPtr SetWinEventHook(
            uint eventMin, uint eventMax, IntPtr hmodWinEventProc, WinEventDelegate lpfnWinEventProc,
            uint idProcess, uint idThread, uint dwFlags);

        [DllImport("user32.dll")]
        private static extern bool UnhookWinEvent(IntPtr hWinEventHook);

        [DllImport("user32.dll")]
        private static extern int GetMessage(out MSG lpMsg, IntPtr hWnd, uint wMsgFilterMin, uint wMsgFilterMax);

        [DllImport("user32.dll")]
        private static extern bool TranslateMessage([In] ref MSG lpMsg);

        [DllImport("user32.dll")]
        private static extern IntPtr DispatchMessage([In] ref MSG lpmsg);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool PostThreadMessage(uint idThread, uint msg, UIntPtr wParam, IntPtr lParam);

        [DllImport("kernel32.dll")]
        private static extern uint GetCurrentThreadId();

        [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
        private static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

        [DllImport("user32.dll")]
        private static extern IntPtr GetAncestor(IntPtr hwnd, uint gaFlags);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr FindWindowEx(IntPtr hwndParent, IntPtr hwndChildAfter, string? lpszClass, string? lpszWindow);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr OpenProcess(uint processAccess, bool bInheritHandle, uint processId);

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern bool QueryFullProcessImageName(IntPtr hProcess, int flags, StringBuilder text, ref int size);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr hObject);

        [StructLayout(LayoutKind.Sequential)]
        private struct MSG
        {
            public IntPtr hwnd;
            public uint message;
            public UIntPtr wParam;
            public IntPtr lParam;
            public uint time;
            public int pt_x;
            public int pt_y;
        }

        private Thread? _staThread;
        private uint _staThreadId;
        private WinEventDelegate? _winEventProc;
        private IntPtr _hookForeground = IntPtr.Zero;
        private IntPtr _hookNameChange = IntPtr.Zero;
        private readonly CancellationTokenSource _cts = new();
        private readonly ManualResetEventSlim _startedEvent = new(false);

        public WindowDetails? CurrentWindow { get; private set; }
        public event EventHandler<WindowDetails>? ActiveWindowChanged;

        public void Start()
        {
            if (_staThread != null) return;

            _staThread = new Thread(RunMessagePump)
            {
                IsBackground = true,
                Name = "MindFlow-WinEventTracker"
            };
            _staThread.SetApartmentState(ApartmentState.STA);
            _staThread.Start();

            _startedEvent.Wait(2000);
        }

        private void RunMessagePump()
        {
            _staThreadId = GetCurrentThreadId();
            _winEventProc = new WinEventDelegate(OnWinEventCallback);

            _hookForeground = SetWinEventHook(
                EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND,
                IntPtr.Zero, _winEventProc, 0, 0,
                WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS);

            _hookNameChange = SetWinEventHook(
                EVENT_OBJECT_NAMECHANGE, EVENT_OBJECT_NAMECHANGE,
                IntPtr.Zero, _winEventProc, 0, 0,
                WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS);

            _startedEvent.Set();

            while (!_cts.IsCancellationRequested)
            {
                int bRet = GetMessage(out var msg, IntPtr.Zero, 0, 0);
                if (bRet <= 0) break; // 0 = WM_QUIT, -1 = error
                TranslateMessage(ref msg);
                DispatchMessage(ref msg);
            }

            if (_hookForeground != IntPtr.Zero) UnhookWinEvent(_hookForeground);
            if (_hookNameChange != IntPtr.Zero) UnhookWinEvent(_hookNameChange);
        }

        private void OnWinEventCallback(
            IntPtr hWinEventHook, uint eventType, IntPtr hwnd, int idObject, int idChild,
            uint dwEventThread, uint dwmsEventTime)
        {
            if (hwnd == IntPtr.Zero || idObject != 0 /* OBJID_WINDOW */) return;

            try
            {
                IntPtr rootHwnd = GetAncestor(hwnd, GA_ROOT);
                if (rootHwnd == IntPtr.Zero) rootHwnd = hwnd;

                var details = QueryWindowDetails(rootHwnd);
                if (details != null && (CurrentWindow == null || CurrentWindow.Hwnd != details.Hwnd || CurrentWindow.Title != details.Title))
                {
                    CurrentWindow = details;
                    var handler = ActiveWindowChanged;
                    if (handler != null)
                    {
                        Task.Run(() =>
                        {
                            try
                            {
                                handler.Invoke(this, details);
                            }
                            catch (Exception ex)
                            {
                                Debug.WriteLine($"Error invoking ActiveWindowChanged handler: {ex.Message}");
                            }
                        });
                    }
                }
            }
            catch
            {
                // Gracefully catch background window destruction races
            }
        }

        public static WindowDetails? QueryWindowDetails(IntPtr hwnd)
        {
            if (hwnd == IntPtr.Zero) return null;

            var sbTitle = new StringBuilder(512);
            GetWindowText(hwnd, sbTitle, sbTitle.Capacity);
            string title = sbTitle.ToString();

            GetWindowThreadProcessId(hwnd, out uint pid);
            string processName = "Unknown";
            string exePath = string.Empty;

            if (pid != 0)
            {
                IntPtr hProcess = OpenProcess(0x1000 /* PROCESS_QUERY_LIMITED_INFORMATION */, false, pid);
                if (hProcess != IntPtr.Zero)
                {
                    try
                    {
                        var sbPath = new StringBuilder(1024);
                        int size = sbPath.Capacity;
                        if (QueryFullProcessImageName(hProcess, 0, sbPath, ref size))
                        {
                            exePath = sbPath.ToString();
                            processName = Path.GetFileName(exePath);
                        }
                    }
                    finally
                    {
                        CloseHandle(hProcess);
                    }
                }

                // Handle UWP ApplicationFrameHost wrapper resolution
                if (string.Equals(processName, "ApplicationFrameHost.exe", StringComparison.OrdinalIgnoreCase))
                {
                    IntPtr childHwnd = FindWindowEx(hwnd, IntPtr.Zero, "Windows.UI.Core.CoreWindow", null);
                    if (childHwnd != IntPtr.Zero)
                    {
                        GetWindowThreadProcessId(childHwnd, out uint childPid);
                        if (childPid != 0 && childPid != pid)
                        {
                            IntPtr hChildProcess = OpenProcess(0x1000, false, childPid);
                            if (hChildProcess != IntPtr.Zero)
                            {
                                try
                                {
                                    var sbChildPath = new StringBuilder(1024);
                                    int childSize = sbChildPath.Capacity;
                                    if (QueryFullProcessImageName(hChildProcess, 0, sbChildPath, ref childSize))
                                    {
                                        exePath = sbChildPath.ToString();
                                        processName = Path.GetFileName(exePath);
                                        pid = childPid;
                                    }
                                }
                                finally
                                {
                                    CloseHandle(hChildProcess);
                                }
                            }
                        }
                    }
                }
            }

            return new WindowDetails(hwnd, title, processName, exePath, pid);
        }

        public void Dispose()
        {
            _cts.Cancel();
            if (_staThreadId != 0)
            {
                PostThreadMessage(_staThreadId, WM_QUIT, UIntPtr.Zero, IntPtr.Zero);
            }

            if (_staThread != null && _staThread.IsAlive)
            {
                _staThread.Join(2000);
            }

            _startedEvent.Dispose();
        }
    }
}
