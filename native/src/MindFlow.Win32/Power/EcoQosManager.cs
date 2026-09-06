/*
Windows 11 EcoQoS and Power Throttling management for thread performance assurance.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Diagnostics;
using System.Runtime.InteropServices;

namespace MindFlow.Win32.Power
{
    public static class EcoQosManager
    {
        private const int ProcessPowerThrottling = 0x26;
        private const uint PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1;
        private const uint PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION = 0x2;

        [StructLayout(LayoutKind.Sequential)]
        private struct PROCESS_POWER_THROTTLING_STATE
        {
            public uint Version;
            public uint ControlMask;
            public uint StateMask;
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetProcessInformation(
            IntPtr hProcess, int ProcessInformationClass,
            ref PROCESS_POWER_THROTTLING_STATE ProcessInformation, uint ProcessInformationSize);

        public static bool DisableEcoQosForCurrentProcess()
        {
            try
            {
                var state = new PROCESS_POWER_THROTTLING_STATE
                {
                    Version = 1,
                    ControlMask = PROCESS_POWER_THROTTLING_EXECUTION_SPEED | PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION,
                    StateMask = 0 // Explicitly disable power throttling
                };

                IntPtr hProcess = Process.GetCurrentProcess().Handle;
                return SetProcessInformation(
                    hProcess, ProcessPowerThrottling,
                    ref state, (uint)Marshal.SizeOf<PROCESS_POWER_THROTTLING_STATE>());
            }
            catch
            {
                return false;
            }
        }
    }
}
