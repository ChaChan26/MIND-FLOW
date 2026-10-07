/*
MainWindow code-behind managing lifecycle, cleanup, and view binding.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using MindFlow.Desktop.ViewModels;
using MindFlow.Win32.Hotkeys;
using MindFlow.Win32.Power;
using MindFlow.Win32.Tray;

namespace MindFlow.Desktop
{
    public partial class MainWindow : Window
    {
        private TrayIconManager? _trayManager;
        private HotkeyManager? _hotkeyManager;
        private bool _isExplicitExit = false;
        private bool _firstMinimizeNotice = true;

        public MainWindow()
        {
            InitializeComponent();
            Loaded += OnWindowLoaded;
        }

        private void OnWindowLoaded(object sender, RoutedEventArgs e)
        {
            IntPtr hwnd = new WindowInteropHelper(this).EnsureHandle();
            HwndSource? source = HwndSource.FromHwnd(hwnd);
            source?.AddHook(WndProc);

            _trayManager = new TrayIconManager();
            _trayManager.Initialize(hwnd, "MIND-FLOW // Cognitive Companion");
            _trayManager.TrayClicked += OnTrayIconClicked;
            _trayManager.TrayRightClicked += OnTrayIconRightClicked;

            _hotkeyManager = new HotkeyManager(hwnd);
            // Win + Alt + F: Toggle Focus Sprint (Start / Pause / Resume)
            _hotkeyManager.Register(KeyModifiers.Windows | KeyModifiers.Alt, 0x46, () =>
            {
                Dispatcher.Invoke(() =>
                {
                    (DataContext as MainViewModel)?.ToggleTimer();
                });
            });

            // Win + Alt + Z: Toggle Zen Sanctuary
            _hotkeyManager.Register(KeyModifiers.Windows | KeyModifiers.Alt, 0x5A, () =>
            {
                Dispatcher.Invoke(() =>
                {
                    RestoreAndActivate();
                    (DataContext as MainViewModel)?.Navigate("zen");
                });
            });

            // Win + Alt + D: Show Focus HUD Dashboard
            _hotkeyManager.Register(KeyModifiers.Windows | KeyModifiers.Alt, 0x44, () =>
            {
                Dispatcher.Invoke(() =>
                {
                    RestoreAndActivate();
                    (DataContext as MainViewModel)?.Navigate("dashboard");
                });
            });

            // Win + Alt + Escape: Hide to Notification Tray
            _hotkeyManager.Register(KeyModifiers.Windows | KeyModifiers.Alt, 0x1B, () =>
            {
                Dispatcher.Invoke(Hide);
            });

            if (DataContext is MainViewModel vm)
            {
                vm.NudgeTriggered += nudge =>
                {
                    Dispatcher.Invoke(() =>
                    {
                        _trayManager?.ShowNotification(nudge.Title, nudge.Message);
                    });
                };

                vm.PropertyChanged += (s, args) =>
                {
                    if (args.PropertyName == nameof(MainViewModel.BatteryCapacityFormatted) ||
                        args.PropertyName == nameof(MainViewModel.CurrentModeName) ||
                        args.PropertyName == nameof(MainViewModel.ActiveProcessName))
                    {
                        string tip = $"MIND-FLOW: {vm.BatteryCapacityFormatted} | {vm.CurrentModeName} ({vm.ActiveProcessName})";
                        _trayManager.UpdateTooltip(tip);
                    }
                };
            }
        }

        private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
        {
            if (_trayManager != null)
            {
                var res = _trayManager.ProcessWindowMessage(hwnd, msg, wParam, lParam, ref handled);
                if (handled) return res;
            }
            if (_hotkeyManager != null)
            {
                if (_hotkeyManager.ProcessMessage(msg, wParam, lParam))
                {
                    handled = true;
                    return IntPtr.Zero;
                }
            }
            return IntPtr.Zero;
        }

        private void OnTrayIconClicked(object? sender, EventArgs e)
        {
            Dispatcher.Invoke(RestoreAndActivate);
        }

        private void OnTrayIconRightClicked(object? sender, EventArgs e)
        {
            Dispatcher.Invoke(ShowTrayContextMenu);
        }

        private void RestoreAndActivate()
        {
            Show();
            if (WindowState == WindowState.Minimized)
            {
                WindowState = WindowState.Normal;
            }
            Activate();
            Focus();
        }

        private void ShowTrayContextMenu()
        {
            var menu = new ContextMenu();

            var openItem = new MenuItem { Header = "✦ Open Focus HUD (Win+Alt+D)" };
            openItem.Click += (s, e) =>
            {
                RestoreAndActivate();
                (DataContext as MainViewModel)?.Navigate("dashboard");
            };
            menu.Items.Add(openItem);

            var zenItem = new MenuItem { Header = "🧘 Zen Sanctuary (Win+Alt+Z)" };
            zenItem.Click += (s, e) =>
            {
                RestoreAndActivate();
                (DataContext as MainViewModel)?.Navigate("zen");
            };
            menu.Items.Add(zenItem);

            var analyticsItem = new MenuItem { Header = "📊 App Usage Analytics" };
            analyticsItem.Click += (s, e) =>
            {
                RestoreAndActivate();
                (DataContext as MainViewModel)?.Navigate("analytics");
            };
            menu.Items.Add(analyticsItem);

            menu.Items.Add(new Separator());

            var sprintItem = new MenuItem { Header = "⚡ Toggle Focus Sprint (Win+Alt+F)" };
            sprintItem.Click += (s, e) => (DataContext as MainViewModel)?.ToggleTimer();
            menu.Items.Add(sprintItem);

            var breakItem = new MenuItem { Header = "☕ Rest Break" };
            breakItem.Click += (s, e) => (DataContext as MainViewModel)?.TakeBreak();
            menu.Items.Add(breakItem);

            menu.Items.Add(new Separator());

            var workProfileItem = new MenuItem { Header = "💼 Switch to Work Workspace" };
            workProfileItem.Click += (s, e) => (DataContext as MainViewModel)?.SwitchWorkspaceProfile("Work");
            menu.Items.Add(workProfileItem);

            var rechargeProfileItem = new MenuItem { Header = "🎮 Switch to Recharge Workspace" };
            rechargeProfileItem.Click += (s, e) => (DataContext as MainViewModel)?.SwitchWorkspaceProfile("Recharge");
            menu.Items.Add(rechargeProfileItem);

            var sweepItem = new MenuItem { Header = "🧹 Sweep Workspace Back to Profiles" };
            sweepItem.Click += (s, e) => (DataContext as MainViewModel)?.SweepWorkspace();
            menu.Items.Add(sweepItem);

            menu.Items.Add(new Separator());

            bool autostartActive = AutostartManager.IsAutostartEnabled();
            var autostartItem = new MenuItem
            {
                Header = "⚙️ Start with Windows",
                IsCheckable = true,
                IsChecked = autostartActive
            };
            autostartItem.Click += (s, e) =>
            {
                bool newState = !autostartActive;
                AutostartManager.SetAutostart(newState);
            };
            menu.Items.Add(autostartItem);

            menu.Items.Add(new Separator());

            var exitItem = new MenuItem { Header = "❌ Exit MIND-FLOW" };
            exitItem.Click += (s, e) =>
            {
                _isExplicitExit = true;
                Close();
            };
            menu.Items.Add(exitItem);

            menu.IsOpen = true;
        }

        protected override void OnClosing(CancelEventArgs e)
        {
            if (!_isExplicitExit)
            {
                e.Cancel = true;
                Hide();
                if (_firstMinimizeNotice)
                {
                    _firstMinimizeNotice = false;
                    _trayManager?.ShowNotification("MIND-FLOW Active", "Running in the system tray. Use Win+Alt+F to toggle focus sprint, Win+Alt+D to open.");
                }
                return;
            }

            _hotkeyManager?.Dispose();
            _trayManager?.Dispose();
            base.OnClosing(e);

            if (DataContext is IDisposable disposable)
            {
                disposable.Dispose();
            }

            Application.Current.Shutdown();
        }
    }
}