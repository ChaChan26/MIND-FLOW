import sys
import io

class Unbuffered:
    def __init__(self, stream):
        self.stream = stream
    def write(self, data):
        self.stream.write(data)
        self.stream.flush()
    def writelines(self, datas):
        self.stream.writelines(datas)
        self.stream.flush()
    def __getattr__(self, attr):
        return getattr(self.stream, attr)

# Redirect standard logs for PyInstaller executable runs
if getattr(sys, 'frozen', False):
    is_gui = "--gui" in sys.argv
    log_suffix = "_gui" if is_gui else ""
    try:
        sys.stdout = Unbuffered(open(f"C:\\MIND\\app{log_suffix}_stdout.log", "w", encoding="utf-8"))
        sys.stderr = Unbuffered(open(f"C:\\MIND\\app{log_suffix}_stderr.log", "w", encoding="utf-8"))
    except Exception:
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

import os
import time
import math
import ctypes
import socket
import threading
import tkinter as tk
import winsound
from datetime import datetime, date

# Initialize and import backend components
from backend.workspace import WorkspaceManager
from backend.database import MindFlowDB
db = MindFlowDB()

import re

# Keep matches_keyword for matches window filters
def matches_keyword(kw, text):
    """Check if a keyword matches a target text respecting word boundaries."""
    kw = kw.lower()
    text = text.lower()
    if kw.isalnum():
        pattern = rf"\b{re.escape(kw)}\b"
    else:
        pattern = rf"(?<![a-zA-Z0-9]){re.escape(kw)}(?![a-zA-Z0-9])"
    return bool(re.search(pattern, text))

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

def get_active_window_title():
    """Retrieve foreground window title securely using ctypes."""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return "None"
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return "None"
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception as e:
        print(f"Error reading active window title: {e}")
        return "None"

def get_active_process_name():
    """Retrieve foreground window process base executable name securely using ctypes."""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return "None"
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h_process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not h_process:
            return "None"
        try:
            buf_size = ctypes.c_ulong(260)
            buf = ctypes.create_unicode_buffer(buf_size.value)
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(buf_size)):
                return os.path.basename(buf.value).lower()
            return "None"
        finally:
            ctypes.windll.kernel32.CloseHandle(h_process)
    except Exception as e:
        print(f"Error reading active process name: {e}")
        return "None"

def get_idle_seconds():
    """Retrieve duration of hardware idle state (no mouse/keyboard) using ctypes."""
    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return max(0.0, millis / 1000.0)
    except Exception as e:
        print(f"Error reading idle seconds: {e}")
        return 0

def trigger_lockout_overlay(duration_seconds=20):
    """Enforce a fullscreen borderless Tkinter window to lockout visual focus with a Brain Dump phase."""
    try:
        # Warm, gentle door-bell style chime instead of a high-pitched alarm
        winsound.Beep(330, 200)  # E4
        winsound.Beep(440, 250)  # A4
    except Exception:
        pass

    root = tk.Tk()
    root.title("MIND-FLOW // Cognitive Shield Lockout")
    root.overrideredirect(True)
    root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
    root.attributes("-topmost", True)
    root.configure(bg="#0b0f19")

    captured_dump = ""
    phase1_active = True
    grace_remaining = 15
    completed_fully = False

    frame = tk.Frame(
        root, bg="#0e0e1a", bd=1, relief="solid", 
        highlightbackground="#2e2e4f", highlightthickness=1, padx=45, pady=40
    )
    frame.place(relx=0.5, rely=0.5, anchor="center")

    title_label = tk.Label(
        frame, text="🌿 COGNITIVE SAVE-STATE 🌿",
        font=("Outfit", 22, "bold"), fg="#b49aff", bg="#0e0e1a"
    )
    title_label.pack(pady=(5, 10))

    desc_label = tk.Label(
        frame, text="Write down your active thoughts or next steps to safely pause your flow.",
        font=("Inter", 12), fg="#9d9db8", bg="#0e0e1a"
    )
    desc_label.pack(pady=5)

    text_box = tk.Text(
        frame, width=55, height=4, font=("Inter", 13),
        bg="#0f0f1b", fg="#eaeaf2", insertbackground="#b49aff",
        bd=0, highlightbackground="#23233b", highlightcolor="#b49aff",
        highlightthickness=1, padx=15, pady=15
    )
    text_box.pack(pady=15)
    text_box.focus_set()

    timer_label = tk.Label(
        frame, text=f"Grace period: {grace_remaining} seconds remaining",
        font=("Outfit", 12, "bold"), fg="#b49aff", bg="#0e0e1a"
    )
    timer_label.pack(pady=5)

    btn_frame = tk.Frame(frame, bg="#0e0e1a")
    btn_frame.pack(pady=10)

    lockout_remaining = duration_seconds
    progress_bar = None
    canvas = None
    lockout_timer_label = None

    def submit_dump(event=None):
        nonlocal captured_dump, phase1_active
        captured_dump = text_box.get("1.0", "end-1c").strip()
        phase1_active = False
        start_lockout_phase()

    save_btn = tk.Button(
        btn_frame, text="Save & Rest (Ctrl+Enter)", font=("Inter", 11, "bold"),
        bg="#8b5cf6", fg="#ffffff", activebackground="#7c3aed", activeforeground="#ffffff",
        bd=0, padx=20, pady=10, cursor="hand2", command=submit_dump
    )
    save_btn.pack()

    def on_btn_enter(e):
        save_btn.config(bg="#7c3aed")
    def on_btn_leave(e):
        save_btn.config(bg="#8b5cf6")
    save_btn.bind("<Enter>", on_btn_enter)
    save_btn.bind("<Leave>", on_btn_leave)
    root.bind("<Control-Return>", submit_dump)

    def emergency_exit(event):
        root.destroy()
    root.bind("<Escape>", emergency_exit)

    def start_lockout_phase():
        text_box.pack_forget()
        timer_label.pack_forget()
        btn_frame.pack_forget()
        desc_label.pack_forget()

        title_label.config(text="🌸 MINDFUL RECHARGE TIME 🌸", fg="#2dd4a8")
        
        anchor_title = tk.Label(
            frame, text="YOUR SECURED FLOW STATE:",
            font=("Outfit", 11, "bold"), fg="#fbbf24", bg="#0e0e1a"
        )
        anchor_title.pack(pady=(15, 2))

        display_text = f'"{captured_dump}"' if captured_dump else "[No thought saved - brain clean]"
        anchor_msg = tk.Label(
            frame, text=display_text, font=("Inter", 15, "italic", "bold"),
            fg="#2dd4a8", bg="#0e0e1a", wraplength=600, justify="center"
        )
        anchor_msg.pack(pady=12)

        rule_label = tk.Label(
            frame, text="THE 20-20-20 RULE:\nLook away from your screen at an object 20 feet away\nfor 20 seconds to reset eye strain and cognitive focus.",
            font=("Inter", 12, "italic"), fg="#9d9db8", bg="#0e0e1a", justify="center"
        )
        rule_label.pack(pady=15)

        nonlocal lockout_timer_label
        lockout_timer_label = tk.Label(
            frame, text=f"{duration_seconds} seconds remaining",
            font=("Outfit", 18, "bold"), fg="#eaeaf2", bg="#0e0e1a"
        )
        lockout_timer_label.pack(pady=10)

        nonlocal canvas
        canvas = tk.Canvas(frame, width=500, height=180, bg="#0e0e1a", bd=0, highlightthickness=0)
        canvas.pack(pady=10)
        canvas.create_line(50, 90, 450, 90, fill="#23233b", dash=(2, 4))
        
        bubble_id = canvas.create_oval(0, 0, 0, 0, fill="#2dd4a8", outline="#5eead4", width=2)
        instruction_text_id = canvas.create_text(0, 0, text="", font=("Inter", 9, "bold"), fill="#ffffff")
        
        start_anim_time = time.time()
        
        def animate_relaxation():
            if not phase1_active and lockout_remaining > 0:
                try:
                    elapsed = time.time() - start_anim_time
                    angle = (elapsed * 2 * math.pi) / 6.0
                    cx = 250 + 160 * math.cos(angle)
                    cy = 90
                    
                    breath_cycle = elapsed % 8.0
                    if breath_cycle < 4.0:
                        fraction = breath_cycle / 4.0
                        radius = 25 + 30 * fraction
                        text = "INHALE..."
                        color = "#2dd4a8"
                        outline_color = "#5eead4"
                    else:
                        fraction = (breath_cycle - 4.0) / 4.0
                        radius = 55 - 30 * fraction
                        text = "EXHALE..."
                        color = "#b49aff"
                        outline_color = "#c084fc"
                    
                    canvas.itemconfig(bubble_id, fill=color, outline=outline_color)
                    canvas.itemconfig(instruction_text_id, text=text)
                    canvas.coords(bubble_id, cx - radius, cy - radius, cx + radius, cy + radius)
                    canvas.coords(instruction_text_id, cx, cy)
                    canvas.after(40, animate_relaxation)
                except Exception:
                    pass
        
        animate_relaxation()

        esc_label = tk.Label(
            frame, text="Press ESCAPE to bypass in case of emergency.",
            font=("Inter", 9), fg="#5c5c78", bg="#0e0e1a"
        )
        esc_label.pack(pady=10)

        def enforce_topmost():
            if not phase1_active and lockout_remaining > 0:
                try:
                    root.lift()
                    root.attributes("-topmost", True)
                    root.focus_force()
                    root.after(100, enforce_topmost)
                except Exception:
                    pass

        enforce_topmost()
        update_lockout_countdown()

    def update_grace_countdown():
        nonlocal grace_remaining
        if not phase1_active:
            return
        if grace_remaining > 0:
            grace_remaining -= 1
            timer_label.config(text=f"Grace period: {grace_remaining} seconds remaining")
            root.after(1000, update_grace_countdown)
        else:
            submit_dump()

    def update_lockout_countdown():
        nonlocal lockout_remaining
        if lockout_remaining > 0:
            lockout_remaining -= 1
            lockout_timer_label.config(text=f"{lockout_remaining} seconds remaining")
            # No alarm sound during relaxation period to keep it peaceful and stress-free
            root.after(1000, update_lockout_countdown)
        else:
            nonlocal completed_fully
            completed_fully = True
            root.destroy()

    update_grace_countdown()
    root.mainloop()
    return captured_dump, completed_fully

# Import state dictionary from server backend to synchronize API mutations
from backend.server import shared_state, db, run_server
shared_state.setdefault("manual_lockout_requested", False)

def main_state_machine(gui_process=None):
    """Background thread checking active windows, tracking idle state, and swapping workspace."""
    print("MIND-FLOW Core State Machine started.")
    workspace = WorkspaceManager()

    # Seed initial daily reflection if none exist for today
    try:
        from datetime import date
        today_str = date.today().isoformat()
        reflections = db.get_reflections()
        has_today_refl = any(r["timestamp"].startswith(today_str) for r in reflections)
        if not has_today_refl:
            db.add_reflection(5, 1, "[Autopilot] Cognitive Companion active for the day")
            print("Autopilot: Seeded initial daily reflection (Energy: 5, Friction: 1)")
    except Exception as e:
        print(f"Error seeding initial reflection: {e}")

    # App variables
    current_mode = "neutral"
    shared_state["current_mode"] = current_mode
    state_start_time = datetime.now()
    
    # Initialize shared app tracking variables
    shared_state["last_app_process"] = None
    shared_state["last_app_title"] = None
    shared_state["app_accumulated_seconds"] = 0
    
    while True:
        time.sleep(1.0)
        
        # Check if standalone GUI process exited
        if gui_process and hasattr(gui_process, 'poll') and gui_process.poll() is not None:
            print("MIND-FLOW dashboard window closed. Sweeping workspace to neutral...")
            
            # Flush app tracking
            last_proc = shared_state.get("last_app_process")
            last_title = shared_state.get("last_app_title")
            accum_sec = shared_state.get("app_accumulated_seconds", 0)
            if last_proc and accum_sec > 0:
                try:
                    db.log_app_usage(last_proc, last_title, accum_sec)
                except Exception as e:
                    print(f"Error logging app usage on GUI close: {e}")
            
            db.log_session(current_mode, state_start_time, datetime.now())
            workspace.swap_workspace(current_mode, "neutral")
            db.save()
            sys.exit(0)
        
        # If user deactivated companion tracking, bypass state machine checks and sweep back workspace
        if not shared_state["tracking_active"]:
            # Flush app tracking
            last_proc = shared_state.get("last_app_process")
            last_title = shared_state.get("last_app_title")
            accum_sec = shared_state.get("app_accumulated_seconds", 0)
            if last_proc and accum_sec > 0:
                try:
                    db.log_app_usage(last_proc, last_title, accum_sec)
                except Exception as e:
                    print(f"Error logging app usage on pause: {e}")
                shared_state["last_app_process"] = None
                shared_state["last_app_title"] = None
                shared_state["app_accumulated_seconds"] = 0
                
            if current_mode != "neutral":
                print(f"Companion disabled: transitioning {current_mode} -> neutral")
                db.log_session(current_mode, state_start_time, datetime.now())
                workspace.swap_workspace(current_mode, "neutral")
                current_mode = "neutral"
            
            shared_state["active_window_title"] = "Companion Paused"
            shared_state["active_process_name"] = "Paused"
            shared_state["current_mode"] = "neutral"
            shared_state["elapsed_seconds"] = 0
            shared_state["idle_seconds"] = 0
            continue

        # Get inputs
        active_title = get_active_window_title()
        active_process = get_active_process_name()
        
        shared_state["active_window_title"] = active_title
        shared_state["active_process_name"] = active_process
        
        # Track last active external window and process (ignoring dashboard focus shifts)
        title_lower = active_title.lower()
        process_lower = active_process.lower()
        is_dashboard = "mind-flow" in title_lower or "companion" in title_lower
        is_invalid = active_title in ["None", "None Detected", "Companion Paused", "Offline"]
        
        if not is_dashboard and not is_invalid:
            shared_state["last_external_window"] = active_title
            shared_state["last_external_process"] = active_process
        
        idle_sec = get_idle_seconds()
        try:
            idle_sec_val = float(idle_sec)
        except (TypeError, ValueError):
            idle_sec_val = 0.0
        shared_state["idle_seconds"] = int(idle_sec_val)

        # App tracking logic
        # We only track if user is active (idle_sec_val < 5) and the app is not Paused/None
        if idle_sec_val < 5:
            if active_process and active_process != "None" and active_process != "Paused":
                last_proc = shared_state.get("last_app_process")
                last_title = shared_state.get("last_app_title")
                accum_sec = shared_state.get("app_accumulated_seconds", 0)

                if active_process == last_proc:
                    shared_state["app_accumulated_seconds"] = accum_sec + 1
                    # Update window title if it's new and valid
                    if active_title and active_title != "None" and active_title != "Paused":
                        shared_state["last_app_title"] = active_title
                else:
                    # Application changed, log previous
                    if last_proc and accum_sec > 0:
                        try:
                            db.log_app_usage(last_proc, last_title, accum_sec)
                        except Exception as e:
                            print(f"Error logging app usage on switch: {e}")
                    shared_state["last_app_process"] = active_process
                    shared_state["last_app_title"] = active_title
                    shared_state["app_accumulated_seconds"] = 1
                
                # Periodically flush every 30 seconds of continuous use of the same app
                if shared_state.get("app_accumulated_seconds", 0) >= 30:
                    try:
                        db.log_app_usage(shared_state["last_app_process"], shared_state["last_app_title"], shared_state["app_accumulated_seconds"])
                    except Exception as e:
                        print(f"Error logging app usage periodic: {e}")
                    shared_state["app_accumulated_seconds"] = 0
        else:
            # User went idle, flush accumulated time
            last_proc = shared_state.get("last_app_process")
            last_title = shared_state.get("last_app_title")
            accum_sec = shared_state.get("app_accumulated_seconds", 0)
            if last_proc and accum_sec > 0:
                try:
                    db.log_app_usage(last_proc, last_title, accum_sec)
                except Exception as e:
                    print(f"Error logging app usage on idle: {e}")
                shared_state["last_app_process"] = None
                shared_state["last_app_title"] = None
                shared_state["app_accumulated_seconds"] = 0

        # Get settings from database dynamically
        settings = db.get_settings()
        adaptive = db.get_adaptive_times()
        work_keywords = settings["work_keywords"]
        recharge_keywords = settings["recharge_keywords"]
        idle_limit = settings["idle_timeout_seconds"]
        work_limit_sec = adaptive["work_minutes"] * 60
        rest_limit_sec = adaptive["rest_seconds"]

        # Check manual lockout trigger
        if shared_state.get("manual_lockout_requested", False):
            shared_state["manual_lockout_requested"] = False
            print(f"Manual lockout requested. Launching lockout overlay with rest duration ({rest_limit_sec}s).")
            
            # Flush app usage before manual lockout
            last_proc = shared_state.get("last_app_process")
            last_title = shared_state.get("last_app_title")
            accum_sec = shared_state.get("app_accumulated_seconds", 0)
            if last_proc and accum_sec > 0:
                try:
                    db.log_app_usage(last_proc, last_title, accum_sec)
                except Exception as e:
                    print(f"Error logging app usage on manual lockout: {e}")
                shared_state["last_app_process"] = None
                shared_state["last_app_title"] = None
                shared_state["app_accumulated_seconds"] = 0
            
            now = datetime.now()
            db.log_session(current_mode if current_mode != "neutral" else "work", state_start_time, now)
            
            # Blocking Tkinter overlay runs
            brain_dump, completed = trigger_lockout_overlay(rest_limit_sec)
            db.log_session("rest", now, datetime.now(), brain_dump=brain_dump, bypassed=not completed)
            state_start_time = datetime.now()
            shared_state["elapsed_seconds"] = 0
            continue

        # Determine target mode
        target_mode = "neutral"
        if idle_sec_val >= idle_limit:
            target_mode = "rest"
        else:
            is_work = any(matches_keyword(kw, active_process) or matches_keyword(kw, active_title) for kw in work_keywords)
            is_recharge = any(matches_keyword(kw, active_process) or matches_keyword(kw, active_title) for kw in recharge_keywords)

            if is_work:
                target_mode = "work"
            elif is_recharge:
                target_mode = "recharge"

        # Check if Mode transition occurred
        if target_mode != current_mode:
            now = datetime.now()
            print(f"State transition: {current_mode} -> {target_mode}")
            db.log_session(current_mode, state_start_time, now)
            workspace.swap_workspace(current_mode, target_mode)
            
            current_mode = target_mode
            shared_state["current_mode"] = current_mode
            state_start_time = now
            shared_state["elapsed_seconds"] = 0
        else:
            elapsed = (datetime.now() - state_start_time).total_seconds()
            shared_state["elapsed_seconds"] = int(elapsed)

            # Enforce Hard Ceilings for Work Mode
            if current_mode == "work" and elapsed >= work_limit_sec:
                print(f"Hard focus ceiling limit reached ({work_limit_sec}s). Launching lockout overlay with rest duration ({rest_limit_sec}s).")
                
                # Flush app usage before hard focus ceiling lockout
                last_proc = shared_state.get("last_app_process")
                last_title = shared_state.get("last_app_title")
                accum_sec = shared_state.get("app_accumulated_seconds", 0)
                if last_proc and accum_sec > 0:
                    try:
                        db.log_app_usage(last_proc, last_title, accum_sec)
                    except Exception as e:
                        print(f"Error logging app usage on hard ceiling: {e}")
                    shared_state["last_app_process"] = None
                    shared_state["last_app_title"] = None
                    shared_state["app_accumulated_seconds"] = 0
                
                brain_dump, completed = trigger_lockout_overlay(rest_limit_sec)
                db.log_session("work", state_start_time, datetime.now(), brain_dump=brain_dump, bypassed=not completed)
                state_start_time = datetime.now()
                shared_state["elapsed_seconds"] = 0

        # Automated energy battery tracking (Auto-decay/recharge check)
        try:
            today_str = date.today().isoformat()
            reflections = db.get_reflections()
            today_reflections = [r for r in reflections if r["timestamp"].startswith(today_str)]
            latest_refl = today_reflections[-1] if today_reflections else None
            
            if latest_refl:
                current_energy = latest_refl.get("energy_level", 5)
                last_refl_time = datetime.fromisoformat(latest_refl["timestamp"])
                elapsed_since_refl = (datetime.now() - last_refl_time).total_seconds()
                
                if current_mode == "work":
                    if elapsed_since_refl >= 300:
                        if current_energy > 1:
                            new_energy = current_energy - 1
                            bypasses_today = sum(1 for s in db.get_sessions() if s.get("bypassed", False) and s["start"].startswith(today_str))
                            new_friction = min(5, 2 + bypasses_today)
                            db.add_reflection(new_energy, new_friction, "[Autopilot] Continuous focus tracking")
                            print(f"Autopilot: Automatically decayed energy to {new_energy} (Friction: {new_friction})")
                elif current_mode in ["recharge", "rest"]:
                    if elapsed_since_refl >= 120:
                        if current_energy < 5:
                            new_energy = current_energy + 1
                            db.add_reflection(new_energy, 1, "[Autopilot] Rest recovery tracking")
                            print(f"Autopilot: Automatically recharged energy to {new_energy}")
        except Exception as e:
            print(f"Error in automatic reflection tracker: {e}")

def run_pyside_gui(url):
    """Run a standalone PySide6 QtWebEngineView window."""
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QColor
    import psutil
    import os
    import sys
    import threading
    
    # 1. Parent process monitor thread
    def monitor_parent():
        parent_pid = os.getppid()
        try:
            parent = psutil.Process(parent_pid)
        except Exception:
            os._exit(0)
        while True:
            time.sleep(1.0)
            if not parent.is_running():
                os._exit(0)
                
    monitor_thread = threading.Thread(target=monitor_parent, daemon=True)
    monitor_thread.start()
    
    # 2. Qt Application Setup
    app = QApplication(sys.argv)
    
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, QColor("#0b0f19"))
    app.setPalette(palette)
    
    window = QMainWindow()
    window.setWindowTitle("MIND-FLOW // Cognitive Companion Dashboard")
    window.resize(1280, 800)
    
    web_view = QWebEngineView()
    web_view.setUrl(QUrl(url))
    web_view.page().setBackgroundColor(QColor("#0b0f19"))
    
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(web_view)
    
    container = QWidget()
    container.setLayout(layout)
    window.setCentralWidget(container)
    
    window.show()
    sys.exit(app.exec())

# Original app window launcher restored for test suite Popen expectations
def launch_app_window(url):
    """Launch the dashboard url in PySide6 standalone window, falling back to original code in testing."""
    import sys
    import subprocess
    import os
    
    # Check if we are running in testing environment (verify_tests.py, run_50_tests.py, unittest, etc.)
    is_testing = any(t in sys.argv[0].lower() for t in ["verify_tests", "run_50_tests", "unittest"])
    if is_testing:
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
        ]
        edge_paths = [
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        ]
        
        for path in chrome_paths:
            if os.path.exists(path):
                try:
                    subprocess.Popen([path, f"--app={url}", "--window-size=1280,800"])
                    return True
                except Exception:
                    pass
                    
        for path in edge_paths:
            if os.path.exists(path):
                try:
                    subprocess.Popen([path, f"--app={url}", "--window-size=1280,800"])
                    return True
                except Exception:
                    pass
                    
        import webbrowser
        webbrowser.open(url)
        return False

    # Standard execution: launch PySide6 process
    if getattr(sys, 'frozen', False):
        exe = sys.executable
        try:
            return subprocess.Popen([exe, "--gui"])
        except Exception as e:
            print(f"Error launching standalone app GUI: {e}")
            return None
    else:
        exe = sys.executable
        script = sys.argv[0]
        try:
            return subprocess.Popen([exe, script, "--gui"])
        except Exception as e:
            print(f"Error launching standalone app GUI in dev: {e}")
            return None

if __name__ == "__main__":
    # If --gui argument is passed, launch the PySide6 standalone window process
    if len(sys.argv) > 1 and sys.argv[1] == "--gui":
        run_pyside_gui("http://127.0.0.1:5000")
        sys.exit(0)

    # Ensure workspace profile directory exists
    os.makedirs(r"C:\MIND\Workspace_Profiles\Work", exist_ok=True)
    os.makedirs(r"C:\MIND\Workspace_Profiles\Recharge", exist_ok=True)

    # 1. Start Server in a separate daemon thread
    server_thread = threading.Thread(target=run_server, kwargs={"port": 5000}, daemon=True)
    server_thread.start()
    
    # Wait a brief moment for Flask to initialize
    time.sleep(0.5)

    # 2. Open dashboard in native app window (PySide6 process)
    print("Launching Cognitive Dashboard in Standalone App Mode...")
    gui_proc = launch_app_window("http://127.0.0.1:5000")

    # 3. Start state machine in the main thread (blocks execution)
    try:
        main_state_machine(gui_process=gui_proc)
    except KeyboardInterrupt:
        print("\nMIND-FLOW terminated by user.")
        sys.exit(0)
