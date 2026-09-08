# Contributors & Authorship Ledger

## Project: MIND-FLOW Cognitive Tracker
**Primary Author & System Architect**: ChaChan26 <minhharry2006@gmail.com>  
**Copyright**: (c) 2026 ChaChan26. All rights reserved.

---

### Core Module Ownership Matrix

| Module / Component | Primary Author | Scope & Description |
| :--- | :--- | :--- |
| `app.py` | ChaChan26 | Core state machine, window telemetry, battery processor, GUI bridge |
| `backend/server.py` | ChaChan26 | Flask REST API, authentication middleware, rate limiting, workspace executor |
| `backend/database.py` | ChaChan26 | SQLite thread-safe connection pooling, WAL journaling, analytical storage |
| `backend/tracker.py` | ChaChan26 | Windows Win32 API window hooks, audio session enumeration, EcoQoS governor |
| `backend/thread_pools.py` | ChaChan26 | Centralized thread pool executor governance and lifecycle management |
| `backend/companion_service.py` | ChaChan26 | CBT companion messaging, advice synthesis, and battery forecasting service |
| `backend/crdt_sync.py` | ChaChan26 | State-based CRDT sync engine with strict lock-ordered concurrency |
| `backend/task_classifier.py`| ChaChan26 | 3-tier regex keyword categorization, browser URL heuristic parser |
| `backend/columnar_analytics.py`| ChaChan26 | DuckDB OLAP aggregation engine for fast time-series queries |
| `backend/workspace_manager.py` | ChaChan26 | Atomic profile file swapping with asynchronous worker threads |
| `backend/nudge_engine.py` | ChaChan26 | Real-time proactive behavioral intervention & flow shield engine |
| `backend/mode_engine.py` | ChaChan26 | Serialized mode transitions & session boundary logging |
| `src/app/App.tsx` | ChaChan26 | React UI root shell, keyboard navigation, theme provider |
| `src/app/components/*` | ChaChan26 | Dashboard, Analytics, FocusTimer, ZenSpace, Achievements, Preferences, BreakOverlay |
| `src/app/types/*` | ChaChan26 | Type contracts, design system themes, Recharts definitions |
| `native/src/MindFlow.Core/*` | ChaChan26 | Native C# domain engine: Cognitive Battery, 3-tier classifier, CRDT, Mode engine, Focus sprint timer, Context switch telemetry |
| `native/src/MindFlow.Win32/*` | ChaChan26 | Native C# Win32 OS telemetry: WinEvent hooks, GetLastInputInfo, Core Audio COM, EcoQoS, Shell_NotifyIcon tray, Autostart manager |
| `native/src/MindFlow.Data/*` | ChaChan26 | Native C# SQLite WAL persistence engine with serialized retry queue, flush semantics, and time-series aggregation |
| `native/src/MindFlow.Desktop/*` | ChaChan26 | Native WPF MVVM desktop UI adhering to Silent Moon design system tokens with multi-screen view triggers and tray minimize |
| `native/tests/*` | ChaChan26 | Native xUnit test suite validating engine math, classification, CRDTs, focus sprint state machine, switching friction, and WAL persistence |
| `tests/*` | ChaChan26 | Hermetic unit & integration test suites with BaseMindFlowTestCase |

---

### Copyright & Intellectual Property Notice
All source code, schemas, mathematical heuristics (Cognitive Battery stamina equation, CBT distortion scanners, flow detection algorithms), UI designs, and configuration assets within this repository are proprietary intellectual property authored by **ChaChan26**.
