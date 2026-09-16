/*
Hardware idle detection utilizing GetLastInputInfo.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Runtime.InteropServices;

namespace MindFlow.Win32.Idle
{
    public static class IdleTracker
    {
        [StructLayout(LayoutKind.Sequential)]
        private struct LASTINPUTINFO
        {
            public uint cbSize;
            public uint dwTime;
        }

        [DllImport("user32.dll")]
        private static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);

        public static double GetIdleSeconds()
        {
            var lii = new LASTINPUTINFO { cbSize = (uint)Marshal.SizeOf<LASTINPUTINFO>() };
            if (!GetLastInputInfo(ref lii)) return 0.0;

            uint tickCount = (uint)Environment.TickCount;
            uint idleTicks = tickCount >= lii.dwTime ? tickCount - lii.dwTime : 0;
            return idleTicks / 1000.0;
        }
    }
}
