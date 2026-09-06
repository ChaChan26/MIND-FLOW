/*
Main ViewModel coordinating in-memory state, high-frequency telemetry, and UI updates without HTTP overhead.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Threading.Tasks;
using System.Windows.Threading;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using MindFlow.Core.Battery;
using MindFlow.Core.Classification;
using MindFlow.Core.State;
using MindFlow.Data.Database;
using MindFlow.Data.Models;
using MindFlow.Win32.Audio;
using MindFlow.Win32.Hooks;
using MindFlow.Win32.Idle;
using MindFlow.Win32.Power;

namespace MindFlow.Desktop.ViewModels
{
    public partial class MainViewModel : ObservableObject, IDisposable
    {
        private readonly CognitiveBattery _battery;
        private readonly TaskClassifier _classifier;
        private readonly ModeEngine _modeEngine;
        private readonly WinEventTracker _winTracker;
        private readonly ComAudioMeter _audioMeter;
        private readonly MindFlowDb _db;
        private readonly DispatcherTimer _tickTimer;
        private readonly DispatcherTimer _zenTimer;

        private DateTime _lastTickTime = DateTime.UtcNow;
        private int _dbFlushCounter = 0;
        private int _zenSeconds = 0;

        [ObservableProperty]
        private double _batteryCapacity = 100.0;

        [ObservableProperty]
        private string _batteryCapacityFormatted = "100%";

        [ObservableProperty]
        private string _consecutiveWorkFormatted = "0m";

        [ObservableProperty]
        private string _currentModeName = "Neutral";

        [ObservableProperty]
        private string _activeProcessName = "Desktop";

        [ObservableProperty]
        private string _activeWindowTitle = "Ready";

        [ObservableProperty]
        private double _idleSeconds = 0.0;

        [ObservableProperty]
        private bool _isAudioActive = false;

        [ObservableProperty]
        private bool _isFlowActive = false;

        [ObservableProperty]
        private string _currentScreen = "dashboard";

        [ObservableProperty]
        private string _breathingPhaseText = "Inhale slowly (4s)";

        [ObservableProperty]
        private double _breathingScale = 1.0;

        [ObservableProperty]
        private string _statusMessage = "Tracking active";

        public ObservableCollection<AppUsageRecord> RecentUsage { get; } = new();

        public MainViewModel()
        {
            // 1. Initialize Core Engines
            _battery = new CognitiveBattery();
            _classifier = new TaskClassifier();
            _modeEngine = new ModeEngine();
            _audioMeter = new ComAudioMeter();
            _winTracker = new WinEventTracker();
            _db = new MindFlowDb();

            // 2. Disable Windows 11 EcoQoS Power Throttling
            EcoQosManager.DisableEcoQosForCurrentProcess();

            // 3. Bind WinEvent Listeners
            _winTracker.ActiveWindowChanged += OnActiveWindowChanged;
            _winTracker.Start();

            // 4. Hook Mode Transition Events
            _modeEngine.ModeChanged += OnModeEngineChanged;

            // 5. Setup 1-Second Telemetry & Battery Tick Loop
            _tickTimer = new DispatcherTimer(DispatcherPriority.Background)
            {
                Interval = TimeSpan.FromSeconds(1)
            };
            _tickTimer.Tick += async (s, e) => await ProcessStateTickAsync();
            _tickTimer.Start();

            // 6. Setup Zen Breathing Loop (4-7-8)
            _zenTimer = new DispatcherTimer(DispatcherPriority.Normal)
            {
                Interval = TimeSpan.FromSeconds(1)
            };
            _zenTimer.Tick += OnZenTick;
            _zenTimer.Start();

            // Load initial persisted data
            _ = LoadInitialDataAsync();
        }

        private async Task LoadInitialDataAsync()
        {
            try
            {
                var state = await _db.GetBatteryStateAsync();
                _battery.Reset(state.Capacity, state.ConsecutiveWorkMinutes);
                BatteryCapacity = _battery.Capacity;
                BatteryCapacityFormatted = $"{Math.Round(_battery.Capacity)}%";
                ConsecutiveWorkFormatted = $"{Math.Round(_battery.ConsecutiveWorkMinutes)}m";

                await RefreshRecentUsageAsync();
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error loading initial DB state: {ex.Message}");
            }
        }

        private void OnActiveWindowChanged(object? sender, WindowDetails details)
        {
            ActiveProcessName = details.ProcessName;
            ActiveWindowTitle = string.IsNullOrWhiteSpace(details.Title) ? details.ProcessName : details.Title;
        }

        private void OnModeEngineChanged(object? sender, ModeChangedEventArgs e)
        {
            CurrentModeName = e.NewMode.ToString();
            IsFlowActive = e.WasFlow;

            // Asynchronously log the ended session to SQLite WAL
            _ = _db.LogSessionAsync(
                e.OldMode.ToString().ToLowerInvariant(),
                e.Timestamp.AddSeconds(-e.DurationSeconds),
                e.Timestamp,
                e.DurationSeconds,
                e.WasFlow);
        }

        private async Task ProcessStateTickAsync()
        {
            DateTime now = DateTime.UtcNow;
            double deltaSeconds = (now - _lastTickTime).TotalSeconds;
            _lastTickTime = now;
            if (deltaSeconds <= 0) deltaSeconds = 1.0;

            double elapsedMinutes = deltaSeconds / 60.0;

            // 1. Read Hardware Idle
            double rawIdle = IdleTracker.GetIdleSeconds();
            bool audioPlaying = _audioMeter.IsAudioPlaying(threshold: 0.015f);
            IsAudioActive = audioPlaying;

            // If audio is actively playing in media/meeting, suppress idle
            double effectiveIdle = audioPlaying ? 0.0 : rawIdle;
            IdleSeconds = Math.Round(effectiveIdle, 1);

            // 2. Classify Current Active Window
            var classifiedMode = _classifier.Classify(ActiveProcessName, ActiveWindowTitle);

            // 3. Advance Mode State Engine
            _modeEngine.EvaluateTick(classifiedMode, effectiveIdle, deltaSeconds);
            CurrentModeName = _modeEngine.CurrentMode.ToString();
            IsFlowActive = _modeEngine.IsCurrentFlowSession;

            // 4. Advance Cognitive Battery Math
            var (cap, workMins) = _battery.ProcessTick(_modeEngine.CurrentMode, elapsedMinutes);
            BatteryCapacity = Math.Round(cap, 1);
            BatteryCapacityFormatted = $"{Math.Round(cap)}%";
            ConsecutiveWorkFormatted = $"{Math.Round(workMins)}m";

            // 5. Aggregate App Usage
            if (!string.IsNullOrWhiteSpace(ActiveProcessName) && ActiveProcessName != "Unknown")
            {
                _ = _db.LogAppUsageAsync(ActiveProcessName, ActiveWindowTitle, deltaSeconds);
            }

            // 6. Periodic Battery Flush to SQLite (every 30 ticks = 30s)
            _dbFlushCounter++;
            if (_dbFlushCounter >= 30)
            {
                _dbFlushCounter = 0;
                await _db.SaveBatteryStateAsync(BatteryCapacity, workMins);
                await RefreshRecentUsageAsync();
            }
        }

        private async Task RefreshRecentUsageAsync()
        {
            try
            {
                var usage = await _db.GetTodayAppUsageAsync();
                RecentUsage.Clear();
                foreach (var item in usage)
                {
                    RecentUsage.Add(item);
                }
            }
            catch { }
        }

        private void OnZenTick(object? sender, EventArgs e)
        {
            _zenSeconds = (_zenSeconds + 1) % 19; // 4s inhale + 7s hold + 8s exhale

            if (_zenSeconds < 4)
            {
                BreathingPhaseText = "Inhale slowly...";
                BreathingScale = 1.0 + (0.35 * ((_zenSeconds + 1) / 4.0));
            }
            else if (_zenSeconds < 11)
            {
                BreathingPhaseText = "Hold gently...";
                BreathingScale = 1.35;
            }
            else
            {
                int exhaleStep = _zenSeconds - 11;
                BreathingPhaseText = "Exhale smoothly...";
                BreathingScale = 1.35 - (0.35 * ((exhaleStep + 1) / 8.0));
            }
        }

        [RelayCommand]
        public void SetMode(string modeName)
        {
            if (Enum.TryParse<ActivityMode>(modeName, true, out var mode))
            {
                _modeEngine.SetManualMode(mode, overrideDurationSeconds: 120);
                CurrentModeName = mode.ToString();
                StatusMessage = $"Locked to {CurrentModeName} for 2 minutes";
            }
        }

        [RelayCommand]
        public void Navigate(string screen)
        {
            CurrentScreen = screen.ToLowerInvariant();
        }

        [RelayCommand]
        public void TakeBreak()
        {
            SetMode("Rest");
            Navigate("zen");
            StatusMessage = "Rest break started";
        }

        [RelayCommand]
        public void ExtendSprint(string? minutesStr)
        {
            if (int.TryParse(minutesStr, out int minutes) && minutes > 0)
            {
                _modeEngine.SetManualMode(ActivityMode.Work, overrideDurationSeconds: minutes * 60);
                CurrentModeName = "Work";
                StatusMessage = $"Sprint extended by {minutes} minutes";
            }
        }

        public void Dispose()
        {
            _tickTimer.Stop();
            _zenTimer.Stop();
            _winTracker.Dispose();
            _audioMeter.Dispose();
            _db.Dispose();
        }
    }
}
