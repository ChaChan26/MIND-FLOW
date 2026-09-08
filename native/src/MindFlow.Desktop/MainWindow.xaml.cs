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
using MindFlow.Win32.Power;
using MindFlow.Win32.Tray;

namespace MindFlow.Desktop
{
    public partial class MainWindow : Window
    {
        private TrayIconManager? _trayManager;
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

            if (DataContext is MainViewModel vm)
            {
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
                return _trayManager.ProcessWindowMessage(hwnd, msg, wParam, lParam, ref handled);
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

            var openItem = new MenuItem { Header = "✦ Open Focus HUD" };
            openItem.Click += (s, e) =>
            {
                RestoreAndActivate();
                (DataContext as MainViewModel)?.Navigate("dashboard");
            };
            menu.Items.Add(openItem);

            var zenItem = new MenuItem { Header = "🧘 Zen Space (4-7-8)" };
            zenItem.Click += (s, e) =>
            {
                RestoreAndActivate();
                (DataContext as MainViewModel)?.Navigate("zen");
            };
            menu.Items.Add(zenItem);

            var analyticsItem = new MenuItem { Header = "📊 App Usage" };
            analyticsItem.Click += (s, e) =>
            {
                RestoreAndActivate();
                (DataContext as MainViewModel)?.Navigate("analytics");
            };
            menu.Items.Add(analyticsItem);

            menu.Items.Add(new Separator());

            var workItem = new MenuItem { Header = "⚡ Extend Sprint (+30m)" };
            workItem.Click += (s, e) => (DataContext as MainViewModel)?.ExtendSprint("30");
            menu.Items.Add(workItem);

            var breakItem = new MenuItem { Header = "☕ Rest Break" };
            breakItem.Click += (s, e) => (DataContext as MainViewModel)?.TakeBreak();
            menu.Items.Add(breakItem);

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
                    _trayManager?.ShowNotification("MIND-FLOW Active", "Running in the system tray to monitor cognitive stamina.");
                }
                return;
            }

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