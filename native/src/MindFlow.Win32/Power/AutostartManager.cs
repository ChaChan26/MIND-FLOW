/*
Windows Registry autostart governor for background daemon launch.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Diagnostics;
using Microsoft.Win32;

namespace MindFlow.Win32.Power
{
    public static class AutostartManager
    {
        private const string RunKeyPath = @"Software\Microsoft\Windows\CurrentVersion\Run";
        private const string AppKeyName = "MIND-FLOW";

        public static bool IsAutostartEnabled()
        {
            try
            {
                using RegistryKey? key = Registry.CurrentUser.OpenSubKey(RunKeyPath, false);
                if (key == null) return false;

                object? value = key.GetValue(AppKeyName);
                if (value is string path && !string.IsNullOrWhiteSpace(path))
                {
                    string currentExe = Environment.ProcessPath ?? string.Empty;
                    return !string.IsNullOrEmpty(currentExe) && path.Contains(currentExe, StringComparison.OrdinalIgnoreCase);
                }
                return false;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[AutostartManager] Error querying autostart registry: {ex.Message}");
                return false;
            }
        }

        public static bool SetAutostart(bool enable)
        {
            try
            {
                using RegistryKey? key = Registry.CurrentUser.OpenSubKey(RunKeyPath, true);
                if (key == null) return false;

                if (enable)
                {
                    string? currentExe = Environment.ProcessPath;
                    if (string.IsNullOrWhiteSpace(currentExe))
                    {
                        return false;
                    }

                    // Wrap in quotes and append --background flag
                    string command = $"\"{currentExe}\" --background";
                    key.SetValue(AppKeyName, command, RegistryValueKind.String);
                    return true;
                }
                else
                {
                    key.DeleteValue(AppKeyName, false);
                    return true;
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[AutostartManager] Error updating autostart registry: {ex.Message}");
                return false;
            }
        }
    }
}
