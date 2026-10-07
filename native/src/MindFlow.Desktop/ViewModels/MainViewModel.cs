/*
Main ViewModel coordinating in-memory state, high-frequency telemetry, and UI updates without HTTP overhead.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Threading;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using MindFlow.Core.Battery;
using MindFlow.Core.Calendar;
using MindFlow.Core.Classification;
using MindFlow.Core.Companion;
using MindFlow.Core.Focus;
using MindFlow.Core.Nudges;
using MindFlow.Core.State;
using MindFlow.Core.Telemetry;
using MindFlow.Core.Workspace;
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
        private readonly ContextSwitchTracker _switchTracker;
        private readonly FocusTimerEngine _focusTimer;
        private readonly WorkspaceManager _workspaceMgr;
        private readonly CognitiveNudgeEngine _nudgeEngine;
        private readonly NudgeSettings _nudgeSettings = new();
        private readonly DispatcherTimer _tickTimer;
        private readonly DispatcherTimer _zenTimer;

        public event Action<NudgeNotification>? NudgeTriggered;

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

        [ObservableProperty]
        private string _timerFormatted = "25:00";

        [ObservableProperty]
        private double _timerProgress = 0.0;

        [ObservableProperty]
        private bool _isTimerRunning = false;

        [ObservableProperty]
        private string _timerSessionLabel = "Sprint";

        [ObservableProperty]
        private int _totalContextSwitches = 0;

        [ObservableProperty]
        private string _switchFrictionText = "Low (Deep Focus)";

        [ObservableProperty]
        private double _switchRatePerMin = 0.0;

        [ObservableProperty]
        private string _companionAdvice = "🌳 Energy optimal. Maintain your stamina by remembering to stretch and hydrate.";

        [ObservableProperty]
        private string _batteryForecast = "Forecast: Stamina optimal. Pace your sprints to sustain focus.";

        [ObservableProperty]
        private string _activeNudgeTitle = string.Empty;

        [ObservableProperty]
        private string _activeNudgeMessage = string.Empty;

        [ObservableProperty]
        private bool _hasActiveNudge = false;

        [ObservableProperty]
        private string _currentWorkspaceProfile = "Work";

        [ObservableProperty]
        private bool _flowShieldEnabled = true;

        [ObservableProperty]
        private bool _eyeCare202020Enabled = true;

        [ObservableProperty]
        private bool _hydrationReminderEnabled = true;

        [ObservableProperty]
        private string _calendarUrl = string.Empty;

        [ObservableProperty]
        private string _calendarSyncStatus = "No calendar connected";

        [ObservableProperty]
        private double _totalWorkHours30d = 0.0;

        [ObservableProperty]
        private double _totalRestHours30d = 0.0;

        [ObservableProperty]
        private double _longestContinuousWorkMins = 0.0;

        [ObservableProperty]
        private double _fatigueRiskScore = 0.0;

        [ObservableProperty]
        private string _fatigueRiskLevel = "Optimal";

        [ObservableProperty]
        private double _todayWorkMins = 0.0;

        [ObservableProperty]
        private double _todayRechargeMins = 0.0;

        [ObservableProperty]
        private double _todayRestMins = 0.0;

        public ObservableCollection<AppUsageRecord> RecentUsage { get; } = new();
        public ObservableCollection<HourlyProductivityRecord> HourlyTrends { get; } = new();
        public ObservableCollection<DailyProductivityTrendRecord> DailyTrends { get; } = new();
        public ObservableCollection<CalendarEventRecord> UpcomingCalendarEvents { get; } = new();

        public MainViewModel()
        {
            try
            {
                // 1. Initialize Core Engines
                _battery = new CognitiveBattery();
                _classifier = new TaskClassifier();
                _modeEngine = new ModeEngine();
                _audioMeter = new ComAudioMeter();
                _winTracker = new WinEventTracker();
                _db = new MindFlowDb();
                _switchTracker = new ContextSwitchTracker();
                _focusTimer = new FocusTimerEngine();
                _nudgeEngine = new CognitiveNudgeEngine();

                string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
                _workspaceMgr = new WorkspaceManager(Path.Combine(appData, "MIND"));

                _focusTimer.SessionCompleted += OnFocusTimerCompleted;
                _focusTimer.TickUpdated += (s, e) =>
                {
                    TimerFormatted = _focusTimer.FormattedTime;
                    TimerProgress = _focusTimer.Progress;
                    IsTimerRunning = _focusTimer.IsRunning;
                    TimerSessionLabel = _focusTimer.IsSprint ? "Sprint" : "Break";
                };

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
            catch (Exception ex)
            {
                Debug.WriteLine($"[MainViewModel] Fatal initialization error: {ex}");
                throw;
            }
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

                int switchesToday = await _db.GetTodayContextSwitchCountAsync();
                _switchTracker.Reset(switchesToday);
                TotalContextSwitches = switchesToday;
                SwitchFrictionText = _switchTracker.FrictionLevelFormatted;
                SwitchRatePerMin = Math.Round(_switchTracker.SwitchesPerMinute, 2);

                await RefreshRecentUsageAsync();
                await RefreshAnalyticsAsync();
                await LoadCalendarEventsAsync();
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error loading initial DB state: {ex.Message}");
            }
        }

        private void OnActiveWindowChanged(object? sender, WindowDetails details)
        {
            Application.Current?.Dispatcher?.InvokeAsync(() =>
            {
                try
                {
                    string oldProc = ActiveProcessName;
                    ActiveProcessName = details.ProcessName;
                    ActiveWindowTitle = string.IsNullOrWhiteSpace(details.Title) ? details.ProcessName : details.Title;

                    if (!string.IsNullOrWhiteSpace(oldProc) && oldProc != "Desktop" && oldProc != "Unknown")
                    {
                        if (_switchTracker.RecordSwitch(oldProc, ActiveProcessName))
                        {
                            _ = _db.LogContextSwitchAsync(oldProc, ActiveProcessName, DateTime.UtcNow);
                            TotalContextSwitches = _switchTracker.TotalSwitchesToday;
                            SwitchFrictionText = _switchTracker.FrictionLevelFormatted;
                            SwitchRatePerMin = Math.Round(_switchTracker.SwitchesPerMinute, 2);
                        }
                    }
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"Error in OnActiveWindowChanged: {ex}");
                }
            });
        }

        private void OnModeEngineChanged(object? sender, ModeChangedEventArgs e)
        {
            Application.Current?.Dispatcher?.InvokeAsync(() =>
            {
                try
                {
                    CurrentModeName = e.NewMode.ToString();
                    IsFlowActive = e.WasFlow;
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"Error in OnModeEngineChanged: {ex}");
                }
            });

            // Asynchronously log the ended session to SQLite WAL
            _ = _db.LogSessionAsync(
                e.OldMode.ToString().ToLowerInvariant(),
                e.Timestamp.AddSeconds(-e.DurationSeconds),
                e.Timestamp,
                e.DurationSeconds,
                e.WasFlow);

            // Asynchronously transition workspace profile shortcuts
            _ = Task.Run(() =>
            {
                try
                {
                    _workspaceMgr.TransitionWorkspace(e.OldMode.ToString(), e.NewMode.ToString());
                }
                catch { }
            });
        }

        private async Task ProcessStateTickAsync()
        {
            try
            {
                DateTime now = DateTime.UtcNow;
                double deltaSeconds = (now - _lastTickTime).TotalSeconds;
                _lastTickTime = now;
                if (deltaSeconds <= 0) deltaSeconds = 1.0;

                double elapsedMinutes = deltaSeconds / 60.0;

                // 1. Advance Focus Timer Engine
                _focusTimer.ProcessTick(deltaSeconds);

                // 2. Read Hardware Idle
                double rawIdle = IdleTracker.GetIdleSeconds();
                bool audioPlaying = _audioMeter.IsAudioPlaying(threshold: 0.015f);
                IsAudioActive = audioPlaying;

                // If audio is actively playing in media/meeting, suppress idle
                double effectiveIdle = audioPlaying ? 0.0 : rawIdle;
                IdleSeconds = Math.Round(effectiveIdle, 1);

                // 3. Classify Current Active Window
                var classifiedMode = _classifier.Classify(ActiveProcessName, ActiveWindowTitle);

                // 4. Advance Mode State Engine
                _modeEngine.EvaluateTick(classifiedMode, effectiveIdle, deltaSeconds);
                CurrentModeName = _modeEngine.CurrentMode.ToString();
                IsFlowActive = _modeEngine.IsCurrentFlowSession;

                // 5. Advance Cognitive Battery Math (with context switch penalty)
                var (cap, workMins) = _battery.ProcessTick(_modeEngine.CurrentMode, elapsedMinutes, _switchTracker.SwitchesPerMinute);
                BatteryCapacity = Math.Round(cap, 1);
                BatteryCapacityFormatted = $"{Math.Round(cap)}%";
                ConsecutiveWorkFormatted = $"{Math.Round(workMins)}m";

                // 6. Aggregate App Usage
                if (!string.IsNullOrWhiteSpace(ActiveProcessName) && ActiveProcessName != "Unknown")
                {
                    _ = _db.LogAppUsageAsync(ActiveProcessName, ActiveWindowTitle, deltaSeconds);
                }

                // 7. Periodic Battery Flush to SQLite (every 30 ticks = 30s)
                _dbFlushCounter++;
                if (_dbFlushCounter >= 30)
                {
                    _dbFlushCounter = 0;
                    await _db.SaveBatteryStateAsync(BatteryCapacity, workMins);
                    await RefreshRecentUsageAsync();
                    await RefreshAnalyticsAsync();
                }

                // 8. Proactive Nudge Evaluation
                _nudgeSettings.EnableDistractionNudges = FlowShieldEnabled;
                _nudgeSettings.EnableEyeCareNudges = EyeCare202020Enabled;
                _nudgeSettings.EnableHydrationNudges = HydrationReminderEnabled;

                double timerElapsed = Math.Max(0.0, _focusTimer.TotalDurationSeconds - _focusTimer.RemainingSeconds);
                var nudge = _nudgeEngine.EvaluateProactiveNudges(
                    _modeEngine.CurrentMode,
                    classifiedMode,
                    ActiveProcessName,
                    ActiveWindowTitle,
                    timerElapsed,
                    _focusTimer.TotalDurationSeconds,
                    BatteryCapacity,
                    IsFlowActive,
                    effectiveIdle,
                    _nudgeSettings,
                    _switchTracker.GetRecentSwitchEpochSeconds());

                if (nudge != null)
                {
                    ActiveNudgeTitle = nudge.Title;
                    ActiveNudgeMessage = nudge.Message;
                    HasActiveNudge = true;
                    NudgeTriggered?.Invoke(nudge);
                }

                // 9. Dynamic CBT Companion Advice & Depletion Forecast
                CompanionAdvice = CompanionService.GenerateCompanionMessage(
                    trackingActive: true,
                    todayBypasses: 0,
                    highStressAlert: SwitchFrictionText.Contains("High"),
                    latestMood: null,
                    currentEnergy: BatteryCapacity,
                    curMode: CurrentModeName);

                BatteryForecast = CompanionService.CalculateBatteryForecast(
                    CurrentModeName,
                    BatteryCapacity,
                    adaptiveRestLimitSeconds: 300);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error in ProcessStateTickAsync: {ex}");
            }
        }

        private async Task RefreshRecentUsageAsync()
        {
            try
            {
                var usage = await _db.GetTodayAppUsageAsync();
                var hourly = await _db.GetTodayHourlyProductivityAsync();
                Application.Current?.Dispatcher?.Invoke(() =>
                {
                    RecentUsage.Clear();
                    foreach (var item in usage)
                    {
                        RecentUsage.Add(item);
                    }

                    HourlyTrends.Clear();
                    foreach (var item in hourly)
                    {
                        HourlyTrends.Add(item);
                    }
                });
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

        private void OnFocusTimerCompleted(object? sender, FocusTimerCompletedEventArgs e)
        {
            try
            {
                System.Media.SystemSounds.Asterisk.Play();
            }
            catch { }

            if (e.SessionType == FocusSessionType.Sprint)
            {
                StatusMessage = $"Sprint finished ({e.TotalMinutes}m). Take a restorative break!";
                _ = _db.LogFocusSessionAsync(e.TotalMinutes, "Focus Sprint", true, _battery.Capacity, Math.Min(100.0, _battery.Capacity + 10.0));
                TakeBreak();
            }
            else
            {
                StatusMessage = "Break completed. Ready for next focus sprint!";
                SetMode("Work");
            }
        }

        [RelayCommand]
        public void StartSprint(string? minutesStr)
        {
            int mins = 25;
            if (int.TryParse(minutesStr, out int val) && val > 0) mins = val;

            _focusTimer.StartSprint(mins);
            _modeEngine.SetManualMode(ActivityMode.Work, overrideDurationSeconds: mins * 60);
            CurrentModeName = "Work";
            StatusMessage = $"Focus sprint started ({mins}m)";
        }

        [RelayCommand]
        public void StartBreakTimer(string? minutesStr)
        {
            int mins = 5;
            if (int.TryParse(minutesStr, out int val) && val > 0) mins = val;

            _focusTimer.StartBreak(mins);
            _modeEngine.SetManualMode(ActivityMode.Rest, overrideDurationSeconds: mins * 60);
            CurrentModeName = "Rest";
            StatusMessage = $"Rest break started ({mins}m)";
        }

        [RelayCommand]
        public void ToggleTimer()
        {
            if (_focusTimer.IsRunning)
            {
                _focusTimer.Pause();
                StatusMessage = "Focus timer paused";
            }
            else if (_focusTimer.State == FocusTimerState.Paused)
            {
                _focusTimer.Resume();
                StatusMessage = "Focus timer resumed";
            }
            else
            {
                StartSprint("25");
            }
        }

        [RelayCommand]
        public void ResetTimer()
        {
            _focusTimer.Reset();
            StatusMessage = "Focus timer reset";
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

        [RelayCommand]
        public void DismissNudge()
        {
            _nudgeEngine.DismissActiveNudge();
            HasActiveNudge = false;
        }

        [RelayCommand]
        public void SnoozeNudge()
        {
            _nudgeEngine.Snooze();
            HasActiveNudge = false;
        }

        [RelayCommand]
        public void SweepWorkspace()
        {
            _ = _workspaceMgr.SweepBackAllAsync();
            StatusMessage = "Workspace swept back to profile folders";
        }

        [RelayCommand]
        public void SwitchWorkspaceProfile(string? profile)
        {
            string target = string.IsNullOrWhiteSpace(profile)
                ? (CurrentWorkspaceProfile == "Work" ? "Recharge" : "Work")
                : profile;
            CurrentWorkspaceProfile = target;
            _ = Task.Run(() => _workspaceMgr.TransitionWorkspace(string.Empty, target));
            StatusMessage = $"Switched to {target} workspace profile";
        }

        [RelayCommand]
        public async Task SyncCalendarAsync()
        {
            if (string.IsNullOrWhiteSpace(CalendarUrl))
            {
                CalendarSyncStatus = "Please enter an iCal feed URL.";
                return;
            }

            try
            {
                CalendarSyncStatus = "Connecting & validating URL...";
                var events = await CalendarSyncEngine.FetchAndParseCalendarAsync(CalendarUrl);
                var tuples = new List<(string Title, string StartTime, string EndTime)>();
                foreach (var ev in events)
                {
                    tuples.Add((ev.Title, ev.StartTime.ToString("o"), ev.EndTime.ToString("o")));
                }

                await _db.SaveCalendarEventsAsync(tuples);
                await LoadCalendarEventsAsync();
                CalendarSyncStatus = $"Synced {events.Count} events successfully.";
            }
            catch (Exception ex)
            {
                CalendarSyncStatus = $"Sync error: {ex.Message}";
            }
        }

        private async Task LoadCalendarEventsAsync()
        {
            try
            {
                var events = await _db.GetCalendarEventsAsync(null);
                Application.Current?.Dispatcher?.Invoke(() =>
                {
                    UpcomingCalendarEvents.Clear();
                    foreach (var ev in events)
                    {
                        UpcomingCalendarEvents.Add(ev);
                    }
                });
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error loading calendar events: {ex.Message}");
            }
        }

        private async Task RefreshAnalyticsAsync()
        {
            try
            {
                var trends = await _db.GetDailyProductivityTrendsAsync(14);
                var fatigue = await _db.GetFatigueDurationAnalyticsAsync(30);
                var todayBreakdown = await _db.GetCategoryBreakdownAsync(DateTime.UtcNow.Date, DateTime.UtcNow.Date.AddDays(1));

                Application.Current?.Dispatcher?.Invoke(() =>
                {
                    DailyTrends.Clear();
                    foreach (var t in trends)
                    {
                        DailyTrends.Add(t);
                    }

                    TotalWorkHours30d = Math.Round(fatigue.TotalWorkSeconds / 3600.0, 1);
                    TotalRestHours30d = Math.Round(fatigue.TotalRestSeconds / 3600.0, 1);
                    LongestContinuousWorkMins = Math.Round(fatigue.LongestContinuousWorkSeconds / 60.0, 1);
                    FatigueRiskScore = fatigue.FatigueRiskScore;

                    if (FatigueRiskScore >= 70.0) FatigueRiskLevel = "High Strain";
                    else if (FatigueRiskScore >= 40.0) FatigueRiskLevel = "Moderate";
                    else FatigueRiskLevel = "Optimal";

                    TodayWorkMins = Math.Round(todayBreakdown.WorkSeconds / 60.0, 1);
                    TodayRechargeMins = Math.Round(todayBreakdown.RechargeSeconds / 60.0, 1);
                    TodayRestMins = Math.Round(todayBreakdown.RestSeconds / 60.0, 1);
                });
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error refreshing analytics: {ex.Message}");
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
