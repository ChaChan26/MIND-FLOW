# MIND-FLOW (Cognitive Productivity Tracker)

MIND-FLOW is a high-performance native Windows desktop application (.NET 8 WPF) designed as a cognitive sanctuary. It tracks active cognitive load in real-time, protects flow state, models energy depletion, provides proactive CBT nudges, and helps you take restorative breaks before burnout occurs.

---

## 🚀 How to Launch the App

### Option 1: Quick Launcher (Recommended)
Double-click **`Launch MIND-FLOW.bat`** in this root directory. It automatically runs the packaged standalone executable, existing Release build, or falls back to `dotnet run`.

### Option 2: Command Line (.NET SDK)
Run from PowerShell or Command Prompt:
```powershell
dotnet run --project native\src\MindFlow.Desktop\MindFlow.Desktop.csproj -c Release
```

---

## 🏗️ Architecture

MIND-FLOW is structured as a modular .NET 8 solution (`native/MindFlow.sln`):

| Project | Description |
|---|---|
| **`MindFlow.Core`** | Pure domain logic: Cognitive battery depletion model, `CognitiveNudgeEngine`, `CompanionService`, task classification, Pomodoro/Flow timer engine, CRDT sync engine (`LWWElementSet`), RFC-5545 `CalendarSyncEngine`, and `WorkspaceManager`. |
| **`MindFlow.Data`** | Local high-throughput data store using SQLite in WAL mode (`PRAGMA journal_mode=WAL;`), schema migrations, 30-day productivity trends, category breakdowns, and fatigue duration analytics. |
| **`MindFlow.Win32`** | Low-level Win32 P/Invoke integrations: `SetWinEventHook` foreground tracking, global hotkeys (`RegisterHotKey`), `GetLastInputInfo` idle detection, system tray lifecycle, and power state telemetry. |
| **`MindFlow.Desktop`** | WPF MVVM user interface, system tray companion menu, HUD stats, and settings overlay. |
| **`MindFlow.Tests`** | Comprehensive xUnit test suite validating all core engines, databases, CRDT sets, nudges, and workspace security. |

---

## 📦 Packaging Standalone Executables

To build a zero-dependency, self-contained single-file binary for distribution:

```powershell
.\native\package_native.ps1
```

The resulting standalone executable will be generated at:
`dist\MIND-FLOW-Native\MIND-FLOW.exe`

---

## 🧪 Running Automated Tests

Run the full xUnit test suite from the repository root:
```powershell
dotnet test native/MindFlow.sln
```
All unit and integration tests run in-memory or on isolated temporary databases with zero side effects.
