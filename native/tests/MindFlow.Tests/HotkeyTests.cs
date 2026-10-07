/*
Unit tests validating Win32 global hotkey registration safeguards and message routing.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using MindFlow.Win32.Hotkeys;
using Xunit;

namespace MindFlow.Tests
{
    public class HotkeyTests
    {
        [Fact]
        public void HotkeyManager_ZeroHandle_FailsGracefully()
        {
            using var manager = new HotkeyManager(IntPtr.Zero);
            int id = manager.Register(KeyModifiers.Windows | KeyModifiers.Alt, 0x46, () => { });
            Assert.Equal(-1, id);
        }

        [Fact]
        public void HotkeyManager_NullCallback_FailsGracefully()
        {
            using var manager = new HotkeyManager((IntPtr)12345);
            int id = manager.Register(KeyModifiers.Windows | KeyModifiers.Alt, 0x46, null!);
            Assert.Equal(-1, id);
        }

        [Fact]
        public void HotkeyManager_ProcessMessage_IgnoresNonHotkeyMessages()
        {
            using var manager = new HotkeyManager(IntPtr.Zero);
            bool handled = manager.ProcessMessage(0x0006 /* WM_ACTIVATE */, IntPtr.Zero, IntPtr.Zero);
            Assert.False(handled);
        }

        [Fact]
        public void HotkeyManager_ProcessMessage_IgnoresUnregisteredId()
        {
            using var manager = new HotkeyManager(IntPtr.Zero);
            bool handled = manager.ProcessMessage(HotkeyManager.WM_HOTKEY, (IntPtr)9999, IntPtr.Zero);
            Assert.False(handled);
        }

        [Fact]
        public void HotkeyManager_Unregister_MissingId_ReturnsFalse()
        {
            using var manager = new HotkeyManager(IntPtr.Zero);
            bool success = manager.Unregister(9999);
            Assert.False(success);
        }

        [Fact]
        public void HotkeyManager_Dispose_CanBeCalledMultipleTimes()
        {
            var manager = new HotkeyManager(IntPtr.Zero);
            manager.Dispose();
            manager.Dispose(); // Verify idempotent cleanup
        }
    }
}
