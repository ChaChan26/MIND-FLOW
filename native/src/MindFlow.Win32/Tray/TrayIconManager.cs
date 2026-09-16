/*
Win32 Shell_NotifyIcon system tray integration with tooltip, balloon alerts, and mouse event routing.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Diagnostics;
using System.Runtime.InteropServices;

namespace MindFlow.Win32.Tray
{
    public class TrayIconManager : IDisposable
    {
        public const int WM_TRAYICON = 0x8100; // WM_APP + 0x100
        private const int NIM_ADD = 0x00000000;
        private const int NIM_MODIFY = 0x00000001;
        private const int NIM_DELETE = 0x00000002;

        private const int NIF_MESSAGE = 0x00000001;
        private const int NIF_ICON = 0x00000002;
        private const int NIF_TIP = 0x00000004;
        private const int NIF_INFO = 0x00000010;

        private const int NIIF_INFO = 0x00000001;

        private const int WM_LBUTTONUP = 0x0202;
        private const int WM_LBUTTONDBLCLK = 0x0203;
        private const int WM_RBUTTONUP = 0x0205;

        private const int IDI_APPLICATION = 32512;

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
        private struct NOTIFYICONDATA
        {
            public int cbSize;
            public IntPtr hWnd;
            public int uID;
            public int uFlags;
            public int uCallbackMessage;
            public IntPtr hIcon;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
            public string szTip;
            public int dwState;
            public int dwStateMask;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)]
            public string szInfo;
            public int uTimeoutOrVersion;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)]
            public string szInfoTitle;
            public int dwInfoFlags;
            public Guid guidItem;
            public IntPtr hBalloonIcon;
        }

        [DllImport("shell32.dll", CharSet = CharSet.Auto)]
        private static extern bool Shell_NotifyIcon(int dwMessage, [In] ref NOTIFYICONDATA lpData);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr LoadIcon(IntPtr hInstance, IntPtr lpIconName);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool DestroyIcon(IntPtr hIcon);

        private IntPtr _hwnd;
        private IntPtr _hIcon;
        private bool _isCreated = false;
        private readonly int _uID = 1001;
        private readonly object _lock = new();

        public event EventHandler? TrayClicked;
        public event EventHandler? TrayRightClicked;

        public bool IsInitialized => _isCreated;

        public bool Initialize(IntPtr hwnd, string initialTip = "MIND-FLOW // Cognitive Companion", IntPtr customIcon = default)
        {
            lock (_lock)
            {
                if (_isCreated) return true;

                _hwnd = hwnd;
                if (customIcon != IntPtr.Zero)
                {
                    _hIcon = customIcon;
                }
                else
                {
                    _hIcon = LoadIcon(IntPtr.Zero, (IntPtr)IDI_APPLICATION);
                }

                NOTIFYICONDATA nid = new NOTIFYICONDATA
                {
                    cbSize = Marshal.SizeOf<NOTIFYICONDATA>(),
                    hWnd = _hwnd,
                    uID = _uID,
                    uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP,
                    uCallbackMessage = WM_TRAYICON,
                    hIcon = _hIcon,
                    szTip = TruncateString(initialTip, 127)
                };

                _isCreated = Shell_NotifyIcon(NIM_ADD, ref nid);
                return _isCreated;
            }
        }

        public void UpdateTooltip(string tooltip)
        {
            lock (_lock)
            {
                if (!_isCreated || _hwnd == IntPtr.Zero) return;

                NOTIFYICONDATA nid = new NOTIFYICONDATA
                {
                    cbSize = Marshal.SizeOf<NOTIFYICONDATA>(),
                    hWnd = _hwnd,
                    uID = _uID,
                    uFlags = NIF_TIP,
                    szTip = TruncateString(tooltip, 127)
                };

                Shell_NotifyIcon(NIM_MODIFY, ref nid);
            }
        }

        public void ShowNotification(string title, string message)
        {
            lock (_lock)
            {
                if (!_isCreated || _hwnd == IntPtr.Zero) return;

                NOTIFYICONDATA nid = new NOTIFYICONDATA
                {
                    cbSize = Marshal.SizeOf<NOTIFYICONDATA>(),
                    hWnd = _hwnd,
                    uID = _uID,
                    uFlags = NIF_INFO,
                    szInfo = TruncateString(message, 255),
                    szInfoTitle = TruncateString(title, 63),
                    dwInfoFlags = NIIF_INFO,
                    uTimeoutOrVersion = 3000
                };

                Shell_NotifyIcon(NIM_MODIFY, ref nid);
            }
        }

        public IntPtr ProcessWindowMessage(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
        {
            if (msg == WM_TRAYICON)
            {
                int mouseMsg = lParam.ToInt32();
                if (mouseMsg == WM_LBUTTONUP || mouseMsg == WM_LBUTTONDBLCLK)
                {
                    TrayClicked?.Invoke(this, EventArgs.Empty);
                    handled = true;
                }
                else if (mouseMsg == WM_RBUTTONUP)
                {
                    TrayRightClicked?.Invoke(this, EventArgs.Empty);
                    handled = true;
                }
            }

            return IntPtr.Zero;
        }

        public void Remove()
        {
            lock (_lock)
            {
                if (!_isCreated || _hwnd == IntPtr.Zero) return;

                NOTIFYICONDATA nid = new NOTIFYICONDATA
                {
                    cbSize = Marshal.SizeOf<NOTIFYICONDATA>(),
                    hWnd = _hwnd,
                    uID = _uID
                };

                Shell_NotifyIcon(NIM_DELETE, ref nid);
                _isCreated = false;
            }
        }

        public void Dispose()
        {
            Remove();
            GC.SuppressFinalize(this);
        }

        private static string TruncateString(string value, int maxLength)
        {
            if (string.IsNullOrEmpty(value)) return string.Empty;
            return value.Length <= maxLength ? value : value.Substring(0, maxLength);
        }
    }
}
