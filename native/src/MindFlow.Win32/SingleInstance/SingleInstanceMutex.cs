/*
Single-Instance Application Mutex and Window Activation.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Runtime.InteropServices;
using System.Threading;

namespace MindFlow.Win32.SingleInstance
{
    public class SingleInstanceMutex : IDisposable
    {
        private const int SW_RESTORE = 9;

        [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
        private static extern IntPtr FindWindow(string? lpClassName, string lpWindowName);

        [DllImport("user32.dll")]
        private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll")]
        private static extern bool SetForegroundWindow(IntPtr hWnd);

        private Mutex? _mutex;
        public bool IsFirstInstance { get; private set; }

        public SingleInstanceMutex(string mutexName = "Local\\MIND_FLOW_SINGLE_INSTANCE_MUTEX")
        {
            try
            {
                _mutex = new Mutex(true, mutexName, out bool createdNew);
                IsFirstInstance = createdNew;
            }
            catch
            {
                IsFirstInstance = true;
            }
        }

        public void ActivateRunningWindow(string windowTitle = "MIND-FLOW // Cognitive Companion")
        {
            try
            {
                IntPtr hwnd = FindWindow(null, windowTitle);
                if (hwnd != IntPtr.Zero)
                {
                    ShowWindow(hwnd, SW_RESTORE);
                    SetForegroundWindow(hwnd);
                }
            }
            catch
            {
                // Best effort window activation
            }
        }

        public void Dispose()
        {
            if (_mutex != null)
            {
                try
                {
                    if (IsFirstInstance)
                        _mutex.ReleaseMutex();
                }
                catch { }
                _mutex.Dispose();
                _mutex = null;
            }
        }
    }
}
