/*
Application startup entry point enforcing single-instance execution and unhandled exception safety.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Diagnostics;
using System.IO;
using System.Windows;
using MindFlow.Win32.SingleInstance;

namespace MindFlow.Desktop
{
    public partial class App : Application
    {
        private SingleInstanceMutex? _singleInstanceMutex;

        protected override void OnStartup(StartupEventArgs e)
        {
            string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            string mindDir = Path.Combine(appData, "MIND");
            Directory.CreateDirectory(mindDir);
            string logPath = Path.Combine(mindDir, "native_startup.log");

            try
            {
                File.WriteAllText(logPath, $"[Startup] Started at {DateTime.Now}\n");
            }
            catch { }

            DispatcherUnhandledException += (sender, args) =>
            {
                try
                {
                    File.AppendAllText(logPath, $"[UnhandledException] {args.Exception}\n");
                    MessageBox.Show($"MIND-FLOW encountered an unexpected error:\n\n{args.Exception.Message}", "MIND-FLOW Native Error", MessageBoxButton.OK, MessageBoxImage.Error);
                }
                catch { }
                // Let the process exit rather than hang invisibly
                args.Handled = false;
            };

            AppDomain.CurrentDomain.UnhandledException += (sender, args) =>
            {
                try
                {
                    File.AppendAllText(logPath, $"[AppDomainException] {args.ExceptionObject}\n");
                }
                catch { }
            };

            TaskScheduler.UnobservedTaskException += (sender, args) =>
            {
                try
                {
                    File.AppendAllText(logPath, $"[UnobservedTaskException] {args.Exception}\n");
                }
                catch { }
                args.SetObserved();
            };

            _singleInstanceMutex = new SingleInstanceMutex("Local\\MIND_FLOW_SINGLE_INSTANCE_MUTEX");
            if (!_singleInstanceMutex.IsFirstInstance)
            {
                try
                {
                    File.AppendAllText(logPath, "[Startup] Mutex check failed: second instance detected.\n");
                }
                catch { }
                _singleInstanceMutex.ActivateRunningWindow("MIND-FLOW // Cognitive Companion");
                Shutdown();
                return;
            }

            try
            {
                File.AppendAllText(logPath, "[Startup] First instance acquired. Calling base.OnStartup.\n");
                base.OnStartup(e);
                File.AppendAllText(logPath, "[Startup] base.OnStartup completed.\n");
            }
            catch (Exception ex)
            {
                File.AppendAllText(logPath, $"[Startup Exception in base.OnStartup] {ex}\n");
            }
        }

        protected override void OnExit(ExitEventArgs e)
        {
            _singleInstanceMutex?.Dispose();
            base.OnExit(e);
        }
    }
}
