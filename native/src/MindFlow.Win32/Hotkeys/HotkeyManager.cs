/*
Win32 Global Hotkey Manager providing system-wide keyboard shortcuts with window hook dispatching.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace MindFlow.Win32.Hotkeys
{
    [Flags]
    public enum KeyModifiers : uint
    {
        None = 0x0000,
        Alt = 0x0001,
        Control = 0x0002,
        Shift = 0x0004,
        Windows = 0x0008,
        NoRepeat = 0x4000
    }

    public class HotkeyManager : IDisposable
    {
        public const int WM_HOTKEY = 0x0312;

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool UnregisterHotKey(IntPtr hWnd, int id);

        private readonly IntPtr _hWnd;
        private readonly Dictionary<int, Action> _registeredActions = new();
        private int _currentId = 9000;
        private bool _disposed = false;

        public HotkeyManager(IntPtr hWnd)
        {
            _hWnd = hWnd;
        }

        public int Register(KeyModifiers modifiers, uint virtualKey, Action callback)
        {
            if (_hWnd == IntPtr.Zero || callback == null) return -1;

            int id = ++_currentId;
            bool success = RegisterHotKey(_hWnd, id, (uint)modifiers, virtualKey);
            if (success)
            {
                _registeredActions[id] = callback;
                return id;
            }
            return -1;
        }

        public bool Unregister(int id)
        {
            if (_registeredActions.ContainsKey(id))
            {
                bool success = UnregisterHotKey(_hWnd, id);
                _registeredActions.Remove(id);
                return success;
            }
            return false;
        }

        public bool ProcessMessage(int msg, IntPtr wParam, IntPtr lParam)
        {
            if (msg == WM_HOTKEY)
            {
                int id = wParam.ToInt32();
                if (_registeredActions.TryGetValue(id, out var callback))
                {
                    callback?.Invoke();
                    return true;
                }
            }
            return false;
        }

        public void Dispose()
        {
            if (!_disposed)
            {
                foreach (var id in _registeredActions.Keys)
                {
                    try { UnregisterHotKey(_hWnd, id); } catch { }
                }
                _registeredActions.Clear();
                _disposed = true;
            }
        }
    }
}
