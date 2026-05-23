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
    try:
        sys.stdout = Unbuffered(open("C:\\MIND\\app_stdout.log", "w", encoding="utf-8"))
        sys.stderr = Unbuffered(open("C:\\MIND\\app_stderr.log", "w", encoding="utf-8"))
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

# Import PySide6 GUI elements
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QPushButton, QProgressBar, QTableWidget, 
    QTableWidgetItem, QStackedWidget, QLineEdit, QTextEdit, QCheckBox, 
    QScrollArea, QFrame, QSizePolicy, QHeaderView, QGraphicsDropShadowEffect
)
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QLinearGradient, QFontDatabase
from PySide6.QtCore import Qt, QPointF, QTimer

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
        winsound.Beep(880, 150)
        winsound.Beep(880, 150)
        winsound.Beep(1200, 300)
    except Exception:
        pass

    root = tk.Tk()
    root.title("MIND-FLOW // Cognitive Shield Lockout")
    root.overrideredirect(True)
    root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
    root.attributes("-topmost", True)
    root.configure(bg="#07070d")

    captured_dump = ""
    phase1_active = True
    grace_remaining = 15
    completed_fully = False

    frame = tk.Frame(
        root, bg="#0e0e1a", bd=1, relief="solid", 
        highlightbackground="#23233b", highlightthickness=1, padx=45, pady=40
    )
    frame.place(relx=0.5, rely=0.5, anchor="center")

    title_label = tk.Label(
        frame, text="MIND-FLOW // COGNITIVE SAVE-STATE",
        font=("Outfit", 22, "bold"), fg="#b49aff", bg="#0e0e1a"
    )
    title_label.pack(pady=(5, 10))

    desc_label = tk.Label(
        frame, text="Dump your active thoughts or next steps before locking out.",
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
        font=("Outfit", 12, "bold"), fg="#ff6b6b", bg="#0e0e1a"
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

        title_label.config(text="MIND-FLOW // COGNITIVE SHIELD ACTIVE", fg="#ff6b6b")
        
        anchor_title = tk.Label(
            frame, text="YOUR ANCHORED MIND STATE:",
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
            if lockout_remaining <= 3 or lockout_remaining % 5 == 0:
                try:
                    winsound.Beep(440, 80)
                except Exception:
                    pass
            root.after(1000, update_lockout_countdown)
        else:
            nonlocal completed_fully
            completed_fully = True
            root.destroy()

    update_grace_countdown()
    root.mainloop()
    return captured_dump, completed_fully

# Import state dictionary from server backend to synchronize API mutations
from backend.server import shared_state, db
shared_state.setdefault("manual_lockout_requested", False)

def main_state_machine():
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
    
    while True:
        time.sleep(1.0)
        
        # If user deactivated companion tracking, bypass state machine checks and sweep back workspace
        if not shared_state["tracking_active"]:
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
        shared_state["idle_seconds"] = int(idle_sec)

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
        if idle_sec >= idle_limit:
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

# Original app window launcher restored for test suite Popen expectations
def launch_app_window(url):
    """Launch the dashboard url in Chrome or Edge app mode to act as a standalone app window."""
    import subprocess
    import os
    
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
                subprocess.Popen([path, f"--app={url}"])
                return True
            except Exception:
                pass
                
    for path in edge_paths:
        if os.path.exists(path):
            try:
                subprocess.Popen([path, f"--app={url}"])
                return True
            except Exception:
                pass
                
    import webbrowser
    webbrowser.open(url)
    return False

# Load premium typography from font files dynamically
def load_fonts():
    font_dir = r"C:\MIND\static\fonts"
    if os.path.exists(font_dir):
        for font_file in os.listdir(font_dir):
            if font_file.endswith(".ttf"):
                path = os.path.join(font_dir, font_file)
                QFontDatabase.addApplicationFont(path)

# Apply graphics drop shadows to simulate premium CSS filters
def apply_shadow_effect(widget, color_str, radius=20, offset=(0, 6)):
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(radius)
    shadow.setColor(QColor(color_str))
    shadow.setOffset(offset[0], offset[1])
    widget.setGraphicsEffect(shadow)

# ----------------- NATIVE PYSIDE6 ROTATING STATUS RING -----------------
class StatusRingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(85, 85)
        self.current_mode = "neutral"
        self.emoji = "💤"
        self.angle = 0
        
        # Anim timer for spinning arcs
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.rotate_ring)
        self.anim_timer.start(30)
        
    def setMode(self, mode, emoji):
        self.current_mode = mode
        self.emoji = emoji
        self.update()
        
    def rotate_ring(self):
        self.angle = (self.angle + 2) % 360
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect().adjusted(4, 4, -4, -4)
        
        colors = {
            "work": ("#b49aff", "rgba(180, 154, 255, 0.1)"),
            "recharge": ("#2dd4a8", "rgba(45, 212, 168, 0.1)"),
            "rest": ("#fbbf24", "rgba(251, 191, 36, 0.1)"),
            "neutral": ("#94a3b8", "rgba(148, 163, 184, 0.1)")
        }
        mode_color_hex, glow_color_hex = colors.get(self.current_mode, colors["neutral"])
        mode_color = QColor(mode_color_hex)
        
        # Draw background ring (faint)
        bg_pen = QPen(QColor("rgba(255, 255, 255, 0.05)"), 3)
        painter.setPen(bg_pen)
        painter.drawEllipse(rect)
        
        # Draw rotating arc
        accent_pen = QPen(mode_color, 3)
        painter.setPen(accent_pen)
        start_angle = self.angle * 16
        span_angle = 120 * 16
        painter.drawArc(rect, start_angle, span_angle)
        
        # Draw dotted counter-rotating outer ring
        outer_rect = self.rect().adjusted(1, 1, -1, -1)
        outer_pen = QPen(QColor(mode_color), 1.5, Qt.DotLine)
        painter.setPen(outer_pen)
        painter.drawArc(outer_rect, -start_angle, 80 * 16)
        
        # Draw Emoji
        painter.setFont(QFont("Segoe UI Emoji", 20))
        painter.drawText(self.rect(), Qt.AlignCenter, self.emoji)

# ----------------- NATIVE PYSIDE6 CUSTOM CHART WIDGET -----------------
class EnergyChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.weekday_data = []
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
    def setData(self, data):
        self.weekday_data = data
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        m_left, m_right, m_top, m_bottom = 50, 30, 30, 40
        chart_w = w - m_left - m_right
        chart_h = h - m_top - m_bottom
        
        # Draw background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#101026")))
        painter.drawRoundedRect(0, 0, w, h, 12, 12)
        
        if not self.weekday_data:
            painter.setPen(QColor("#7878a3"))
            painter.setFont(QFont("Inter", 11))
            painter.drawText(self.rect(), Qt.AlignCenter, "Collect reflections to compile Weekly Map")
            return
            
        grid_pen = QPen(QColor("rgba(255, 255, 255, 0.04)"), 1)
        text_pen = QPen(QColor("#7878a3"))
        painter.setFont(QFont("Inter", 9))
        
        # Grid lines
        for val in range(1, 6):
            y = m_top + chart_h - ((val - 1) / 4) * chart_h
            painter.setPen(grid_pen)
            painter.drawLine(m_left, y, w - m_right, y)
            painter.setPen(text_pen)
            painter.drawText(m_left - 25, y + 4, str(val))
            
        energy_points = []
        friction_points = []
        num_days = len(self.weekday_data)
        
        for i, day in enumerate(self.weekday_data):
            x = m_left + (i / max(1, num_days - 1)) * chart_w
            painter.setPen(text_pen)
            painter.drawText(x - 20, h - m_bottom + 18, 40, 15, Qt.AlignCenter, day["day"])
            
            if day.get("count", 0) > 0:
                e_val = day["avg_energy"]
                f_val = day["avg_friction"]
                y_e = m_top + chart_h - ((e_val - 1) / 4) * chart_h
                y_f = m_top + chart_h - ((f_val - 1) / 4) * chart_h
                energy_points.append(QPointF(x, y_e))
                friction_points.append(QPointF(x, y_f))
                
        # Draw area gradients
        if len(energy_points) > 1:
            path = QPainterPath()
            path.moveTo(energy_points[0].x(), m_top + chart_h)
            for pt in energy_points:
                path.lineTo(pt)
            path.lineTo(energy_points[-1].x(), m_top + chart_h)
            path.closeSubpath()
            grad = QLinearGradient(0, m_top, 0, m_top + chart_h)
            grad.setColorAt(0, QColor("rgba(45, 212, 168, 0.12)"))
            grad.setColorAt(1, QColor("rgba(45, 212, 168, 0.0)"))
            painter.fillPath(path, QBrush(grad))
            
        if len(friction_points) > 1:
            path = QPainterPath()
            path.moveTo(friction_points[0].x(), m_top + chart_h)
            for pt in friction_points:
                path.lineTo(pt)
            path.lineTo(friction_points[-1].x(), m_top + chart_h)
            path.closeSubpath()
            grad = QLinearGradient(0, m_top, 0, m_top + chart_h)
            grad.setColorAt(0, QColor("rgba(180, 154, 255, 0.12)"))
            grad.setColorAt(1, QColor("rgba(180, 154, 255, 0.0)"))
            painter.fillPath(path, QBrush(grad))
            
        # Draw lines
        border_pen = QPen(QColor("#0c0c1b"), 1.5)
        
        if len(energy_points) > 1:
            pen = QPen(QColor("#2dd4a8"), 3, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(energy_points[0])
            for pt in energy_points[1:]:
                path.lineTo(pt)
            painter.drawPath(path)
            
            painter.setBrush(QBrush(QColor("#2dd4a8")))
            for pt in energy_points:
                painter.setPen(border_pen)
                painter.drawEllipse(pt, 4.5, 4.5)
                
        if len(friction_points) > 1:
            pen = QPen(QColor("#b49aff"), 3, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(friction_points[0])
            for pt in friction_points[1:]:
                path.lineTo(pt)
            painter.drawPath(path)
            
            painter.setBrush(QBrush(QColor("#b49aff")))
            for pt in friction_points:
                painter.setPen(border_pen)
                painter.drawEllipse(pt, 4.5, 4.5)

# ----------------- QSS STYLESHEET DEFINITION -----------------
QSS_STYLE = """
QMainWindow {
    background-color: #0c0c1b;
}
QWidget#centralWidget {
    background-color: #0c0c1b;
}
QFrame#sidebar {
    background-color: #121228;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}
QLabel#brandText {
    font-size: 16px;
    font-weight: bold;
    color: #eaeaf2;
    font-family: 'Outfit';
}
QLabel#brandSub {
    font-size: 10px;
    color: #7878a3;
    font-weight: bold;
    font-family: 'Outfit';
}
QPushButton.nav-btn {
    text-align: left;
    background-color: transparent;
    color: #adadc9;
    padding: 12px 18px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    font-family: 'Inter';
}
QPushButton.nav-btn:hover {
    background-color: rgba(255, 255, 255, 0.04);
    color: #eaeaf2;
}
QPushButton.nav-btn.active {
    background-color: rgba(180, 154, 255, 0.08);
    color: #b49aff;
    border-left: 3px solid #b49aff;
    border-radius: 0px 8px 8px 0px;
}
QFrame.Card {
    background-color: #14142f;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
}
QLabel.card-title {
    font-size: 14px;
    font-weight: bold;
    color: #eaeaf2;
    font-family: 'Outfit';
}
QLabel.card-desc {
    font-size: 11px;
    color: #adadc9;
    font-family: 'Inter';
}
QPushButton.rate-btn {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    color: #adadc9;
    padding: 8px;
    font-size: 12px;
}
QPushButton.rate-btn:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #eaeaf2;
}
QPushButton.action-btn {
    background-color: #7c3aed;
    color: white;
    padding: 10px 18px;
    border-radius: 8px;
    font-weight: bold;
    font-size: 12px;
    font-family: 'Inter';
}
QPushButton.action-btn:hover {
    background-color: #6d28d9;
}
QPushButton.secondary-btn {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #eaeaf2;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 12px;
}
QPushButton.secondary-btn:hover {
    background-color: rgba(255, 255, 255, 0.1);
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.1);
    min-height: 20px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 0.2);
}
QLineEdit, QTextEdit, QSpinBox {
    background-color: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    color: #eaeaf2;
    padding: 8px 12px;
    font-size: 12px;
    font-family: 'Inter';
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {
    border: 1px solid #b49aff;
}
QTableWidget {
    background-color: transparent;
    gridline-color: rgba(255, 255, 255, 0.03);
    border: none;
    color: #adadc9;
    font-size: 12px;
    font-family: 'Inter';
}
QTableWidget::item {
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}
QHeaderView::section {
    background-color: transparent;
    color: #7878a3;
    padding: 8px;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    font-weight: bold;
    text-transform: uppercase;
    font-size: 10px;
    font-family: 'Outfit';
}
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MIND-FLOW // Cognitive Companion")
        self.resize(1180, 780)
        
        # Central frame
        self.main_widget = QWidget()
        self.main_widget.setObjectName("centralWidget")
        self.setCentralWidget(self.main_widget)
        
        layout = QHBoxLayout(self.main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 1. Sidebar Panel
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(240)
        layout.addWidget(self.sidebar)
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(20, 25, 20, 25)
        sidebar_layout.setSpacing(15)
        
        # Sidebar Logo Header
        brand_layout = QHBoxLayout()
        logo_lbl = QLabel("🧠")
        logo_lbl.setStyleSheet("font-size: 22px;")
        brand_text_layout = QVBoxLayout()
        brand_title = QLabel("MIND-FLOW")
        brand_title.setObjectName("brandText")
        brand_sub = QLabel("COGNITIVE SHIELD")
        brand_sub.setObjectName("brandSub")
        brand_text_layout.addWidget(brand_title)
        brand_text_layout.addWidget(brand_sub)
        brand_layout.addWidget(logo_lbl)
        brand_layout.addLayout(brand_text_layout)
        sidebar_layout.addLayout(brand_layout)
        
        sidebar_layout.addSpacing(25)
        
        # Navigation Buttons
        self.btn_dashboard = QPushButton("⚡  Dashboard")
        self.btn_dashboard.setCursor(Qt.PointingHandCursor)
        self.btn_dashboard.setObjectName("nav-btn-dashboard")
        self.btn_dashboard.setProperty("class", "nav-btn")
        self.btn_dashboard.clicked.connect(lambda: self.switch_tab("dashboard"))
        sidebar_layout.addWidget(self.btn_dashboard)
        
        self.btn_analytics = QPushButton("📊  Energy Map")
        self.btn_analytics.setCursor(Qt.PointingHandCursor)
        self.btn_analytics.setObjectName("nav-btn-analytics")
        self.btn_analytics.setProperty("class", "nav-btn")
        self.btn_analytics.clicked.connect(lambda: self.switch_tab("analytics"))
        sidebar_layout.addWidget(self.btn_analytics)
        
        self.btn_settings = QPushButton("⚙️  Preferences")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setObjectName("nav-btn-settings")
        self.btn_settings.setProperty("class", "nav-btn")
        self.btn_settings.clicked.connect(lambda: self.switch_tab("settings"))
        sidebar_layout.addWidget(self.btn_settings)
        
        sidebar_layout.addStretch()
        
        # Sidebar Status Indicators Panel
        status_panel = QFrame()
        status_panel.setStyleSheet("background-color: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px; padding: 12px;")
        status_panel_layout = QVBoxLayout(status_panel)
        status_panel_layout.setSpacing(10)
        
        self.lbl_tracking_status = QLabel("Shield Active")
        self.lbl_tracking_status.setStyleSheet("font-size: 11px; color: #2dd4a8; font-weight: bold; font-family: 'Outfit';")
        status_panel_layout.addWidget(self.lbl_tracking_status)
        
        self.btn_toggle_tracking = QPushButton("Pause Companion")
        self.btn_toggle_tracking.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_tracking.setStyleSheet("background-color: rgba(255, 255, 255, 0.04); font-size: 11px; padding: 6px; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 6px; font-family: 'Inter';")
        self.btn_toggle_tracking.clicked.connect(self.toggle_tracking)
        status_panel_layout.addWidget(self.btn_toggle_tracking)
        
        self.btn_close_app = QPushButton("Close App")
        self.btn_close_app.setCursor(Qt.PointingHandCursor)
        self.btn_close_app.setStyleSheet("background-color: rgba(239, 68, 68, 0.08); font-size: 11px; color: #ff6b6b; padding: 6px; border: 1px solid rgba(239, 68, 68, 0.15); border-radius: 6px; font-family: 'Inter';")
        self.btn_close_app.clicked.connect(self.close)
        status_panel_layout.addWidget(self.btn_close_app)
        
        sidebar_layout.addWidget(status_panel)
        
        # 2. Main Content Screens (Stacked View)
        self.pages = QStackedWidget()
        self.pages.setStyleSheet("background-color: #0c0c1b; padding: 30px;")
        layout.addWidget(self.pages)
        
        # Load Tabs
        self.build_dashboard_tab()
        self.build_analytics_tab()
        self.build_settings_tab()
        
        # Set Active Tab
        self.switch_tab("dashboard")
        
        self.selected_energy = 5
        self.selected_friction = 2
        
        # Polling updates timer (runs at 1 second intervals safely)
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll_shared_state)
        self.timer.start(1000)
        
    def switch_tab(self, tab):
        self.btn_dashboard.setStyleSheet("")
        self.btn_dashboard.setProperty("class", "nav-btn")
        self.btn_analytics.setStyleSheet("")
        self.btn_analytics.setProperty("class", "nav-btn")
        self.btn_settings.setStyleSheet("")
        self.btn_settings.setProperty("class", "nav-btn")
        
        self.btn_dashboard.style().unpolish(self.btn_dashboard)
        self.btn_dashboard.style().polish(self.btn_dashboard)
        self.btn_analytics.style().unpolish(self.btn_analytics)
        self.btn_analytics.style().polish(self.btn_analytics)
        self.btn_settings.style().unpolish(self.btn_settings)
        self.btn_settings.style().polish(self.btn_settings)
        
        if tab == "dashboard":
            self.pages.setCurrentIndex(0)
            self.btn_dashboard.setStyleSheet("background-color: rgba(180, 154, 255, 0.08); color: #b49aff; border-left: 3px solid #b49aff; border-radius: 0px 8px 8px 0px;")
        elif tab == "analytics":
            self.pages.setCurrentIndex(1)
            self.btn_analytics.setStyleSheet("background-color: rgba(180, 154, 255, 0.08); color: #b49aff; border-left: 3px solid #b49aff; border-radius: 0px 8px 8px 0px;")
            self.load_analytics_data()
        elif tab == "settings":
            self.pages.setCurrentIndex(2)
            self.btn_settings.setStyleSheet("background-color: rgba(180, 154, 255, 0.08); color: #b49aff; border-left: 3px solid #b49aff; border-radius: 0px 8px 8px 0px;")
            self.load_settings_data()

    # ----------------- TAB 1: FOCUS DASHBOARD -----------------
    def build_dashboard_tab(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(20)
        
        # Header
        h_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        header_title = QLabel("Your Focus Dashboard")
        header_title.setStyleSheet("font-family: 'Outfit'; font-size: 24px; font-weight: bold; color: #eaeaf2;")
        header_sub = QLabel("Real-time energy tracking and mindful focus insights.")
        header_sub.setStyleSheet("font-size: 13px; color: #adadc9; font-family: 'Inter';")
        title_box.addWidget(header_title)
        title_box.addWidget(header_sub)
        
        self.lbl_clock = QLabel("10:15 AM")
        self.lbl_clock.setStyleSheet("font-size: 12px; background-color: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); padding: 5px 12px; border-radius: 12px; color: #adadc9; font-family: 'Inter';")
        
        h_layout.addLayout(title_box)
        h_layout.addStretch()
        h_layout.addWidget(self.lbl_clock)
        page_layout.addLayout(h_layout)
        
        # Banner message
        self.banner = QFrame()
        self.banner.setStyleSheet("background-color: rgba(180, 154, 255, 0.04); border: 1px solid rgba(180, 154, 255, 0.15); border-radius: 12px; padding: 12px;")
        banner_layout = QHBoxLayout(self.banner)
        shield_emoji = QLabel("🛡️")
        shield_emoji.setStyleSheet("font-size: 16px;")
        self.banner_text = QLabel("Your companion is watching over you. Looking good!")
        self.banner_text.setStyleSheet("font-size: 12px; color: #eaeaf2; font-family: 'Inter';")
        banner_layout.addWidget(shield_emoji)
        banner_layout.addWidget(self.banner_text)
        banner_layout.addStretch()
        page_layout.addWidget(self.banner)
        
        # Grid of Widgets
        grid = QGridLayout()
        grid.setSpacing(20)
        
        # Widget 1: Daily Mental Battery Card
        self.battery_card = QFrame()
        self.battery_card.setProperty("class", "Card")
        apply_shadow_effect(self.battery_card, "rgba(0, 0, 0, 0.3)", 20)
        
        bat_layout = QVBoxLayout(self.battery_card)
        bat_layout.setContentsMargins(18, 18, 18, 18)
        
        title_hl = QHBoxLayout()
        bat_title = QLabel("Daily Mental Battery")
        bat_title.setProperty("class", "card-title")
        self.lbl_battery_state = QLabel("⚡ discharging")
        self.lbl_battery_state.setStyleSheet("font-size: 11px; color: #ff6b6b; font-weight: bold; font-family: 'Outfit';")
        title_hl.addWidget(bat_title)
        title_hl.addStretch()
        title_hl.addWidget(self.lbl_battery_state)
        bat_layout.addLayout(title_hl)
        
        battery_flex = QHBoxLayout()
        battery_flex.setSpacing(15)
        
        self.battery_bar = QProgressBar()
        self.battery_bar.setValue(100)
        self.battery_bar.setTextVisible(False)
        self.battery_bar.setFixedHeight(30)
        self.battery_bar.setFixedWidth(200)
        self.battery_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                background-color: rgba(0, 0, 0, 0.2);
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 6px;
            }
        """)
        battery_flex.addWidget(self.battery_bar)
        
        self.lbl_battery_pct = QLabel("100%")
        self.lbl_battery_pct.setStyleSheet("font-family: 'Outfit'; font-size: 24px; font-weight: bold; color: #eaeaf2;")
        battery_flex.addWidget(self.lbl_battery_pct)
        battery_flex.addStretch()
        bat_layout.addLayout(battery_flex)
        
        self.lbl_battery_msg = QLabel("Fully Charged. Safe to perform deep work.")
        self.lbl_battery_msg.setStyleSheet("font-size: 11px; color: #adadc9; margin-top: 5px; font-family: 'Inter';")
        bat_layout.addWidget(self.lbl_battery_msg)
        
        # Divider line
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("background-color: rgba(255, 255, 255, 0.05); height: 1px; border: none;")
        bat_layout.addWidget(div)
        
        # Mini durations list
        durations_layout = QHBoxLayout()
        
        item_work = QVBoxLayout()
        lbl_w = QLabel("💻 Work Time")
        lbl_w.setStyleSheet("font-size: 10px; color: #7878a3; font-weight: bold; font-family: 'Outfit';")
        self.lbl_stat_work = QLabel("0h 0m")
        self.lbl_stat_work.setStyleSheet("font-family: 'Outfit'; font-size: 14px; font-weight: bold; color: #eaeaf2;")
        item_work.addWidget(lbl_w)
        item_work.addWidget(self.lbl_stat_work)
        durations_layout.addLayout(item_work)
        
        item_recharge = QVBoxLayout()
        lbl_r = QLabel("🎮 Recharge")
        lbl_r.setStyleSheet("font-size: 10px; color: #7878a3; font-weight: bold; font-family: 'Outfit';")
        self.lbl_stat_recharge = QLabel("0h 0m")
        self.lbl_stat_recharge.setStyleSheet("font-family: 'Outfit'; font-size: 14px; font-weight: bold; color: #eaeaf2;")
        item_recharge.addWidget(lbl_r)
        item_recharge.addWidget(self.lbl_stat_recharge)
        durations_layout.addLayout(item_recharge)
        
        item_rest = QVBoxLayout()
        lbl_s = QLabel("💤 Rest Time")
        lbl_s.setStyleSheet("font-size: 10px; color: #7878a3; font-weight: bold; font-family: 'Outfit';")
        self.lbl_stat_rest = QLabel("0h 0m")
        self.lbl_stat_rest.setStyleSheet("font-family: 'Outfit'; font-size: 14px; font-weight: bold; color: #eaeaf2;")
        item_rest.addWidget(lbl_s)
        item_rest.addWidget(self.lbl_stat_rest)
        durations_layout.addLayout(item_rest)
        
        bat_layout.addLayout(durations_layout)
        grid.addWidget(self.battery_card, 0, 0, 1, 2)
        
        # Widget 2: Shield Status Card
        self.shield_card = QFrame()
        self.shield_card.setProperty("class", "Card")
        apply_shadow_effect(self.shield_card, "rgba(0, 0, 0, 0.3)", 20)
        
        shield_layout = QVBoxLayout(self.shield_card)
        shield_layout.setContentsMargins(18, 18, 18, 18)
        
        title_sc = QLabel("Shield Status")
        title_sc.setProperty("class", "card-title")
        shield_layout.addWidget(title_sc)
        
        sc_flex = QHBoxLayout()
        
        # Rotating Vector Arc indicator
        self.shield_ring = StatusRingWidget()
        self.shield_ring.setMode("neutral", "💤")
        
        sc_details = QVBoxLayout()
        self.lbl_shield_mode = QLabel("Rest Mode")
        self.lbl_shield_mode.setStyleSheet("font-size: 14px; font-weight: bold; color: #eaeaf2; font-family: 'Outfit';")
        self.lbl_block_timer = QLabel("00:00")
        self.lbl_block_timer.setStyleSheet("font-family: 'Outfit'; font-size: 20px; font-weight: bold; color: #fbbf24;")
        self.lbl_shield_badge = QLabel("Default")
        self.lbl_shield_badge.setStyleSheet("font-size: 9px; color: #adadc9; background-color: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); padding: 2px 6px; border-radius: 4px; font-family: 'Inter';")
        
        sc_details.addWidget(self.lbl_shield_mode)
        sc_details.addWidget(self.lbl_block_timer)
        sc_details.addWidget(self.lbl_shield_badge)
        
        sc_flex.addWidget(self.shield_ring)
        sc_flex.addLayout(sc_details)
        sc_flex.addStretch()
        shield_layout.addLayout(sc_flex)
        
        div_sc = QFrame()
        div_sc.setFrameShape(QFrame.HLine)
        div_sc.setStyleSheet("background-color: rgba(255, 255, 255, 0.05); height: 1px; border: none;")
        shield_layout.addWidget(div_sc)
        
        app_disp = QVBoxLayout()
        app_lbl = QLabel("Foreground Application:")
        app_lbl.setStyleSheet("font-size: 10px; color: #7878a3; font-family: 'Inter';")
        self.lbl_foreground_app = QLabel("None Detected")
        self.lbl_foreground_app.setStyleSheet("font-family: 'Outfit'; font-size: 12px; font-weight: bold; color: #eaeaf2;")
        self.lbl_foreground_process = QLabel("Process: None")
        self.lbl_foreground_process.setStyleSheet("font-size: 9px; color: #7878a3; font-family: 'Inter';")
        app_disp.addWidget(app_lbl)
        app_disp.addWidget(self.lbl_foreground_app)
        app_disp.addWidget(self.lbl_foreground_process)
        
        self.app_actions_box = QWidget()
        action_btn_layout = QHBoxLayout(self.app_actions_box)
        action_btn_layout.setContentsMargins(0, 5, 0, 0)
        action_btn_layout.setSpacing(10)
        
        self.btn_add_work_kw = QPushButton("+ Work")
        self.btn_add_work_kw.setCursor(Qt.PointingHandCursor)
        self.btn_add_work_kw.setStyleSheet("background-color: rgba(180, 154, 255, 0.1); border: 1px solid rgba(180, 154, 255, 0.2); font-size: 10px; padding: 4px 8px; color: #b49aff; border-radius: 4px; font-family: 'Inter'; font-weight: bold;")
        self.btn_add_work_kw.clicked.connect(lambda: self.quick_add_keyword("work"))
        
        self.btn_add_recharge_kw = QPushButton("+ Recharge")
        self.btn_add_recharge_kw.setCursor(Qt.PointingHandCursor)
        self.btn_add_recharge_kw.setStyleSheet("background-color: rgba(45, 212, 168, 0.1); border: 1px solid rgba(45, 212, 168, 0.2); font-size: 10px; padding: 4px 8px; color: #2dd4a8; border-radius: 4px; font-family: 'Inter'; font-weight: bold;")
        self.btn_add_recharge_kw.clicked.connect(lambda: self.quick_add_keyword("recharge"))
        
        action_btn_layout.addWidget(self.btn_add_work_kw)
        action_btn_layout.addWidget(self.btn_add_recharge_kw)
        app_disp.addWidget(self.app_actions_box)
        
        shield_layout.addLayout(app_disp)
        grid.addWidget(self.shield_card, 0, 2, 1, 1)
        
        # Widget 3: Workspace Portal Card
        self.portal_card = QFrame()
        self.portal_card.setProperty("class", "Card")
        apply_shadow_effect(self.portal_card, "rgba(0, 0, 0, 0.3)", 20)
        
        portal_layout = QVBoxLayout(self.portal_card)
        portal_layout.setContentsMargins(18, 18, 18, 18)
        
        title_pc = QLabel("Workspace Portal")
        title_pc.setProperty("class", "card-title")
        portal_layout.addWidget(title_pc)
        
        lbl_pc_desc = QLabel("The folder Desktop/Current_Workspace is synced to this portal.")
        lbl_pc_desc.setWordWrap(True)
        lbl_pc_desc.setStyleSheet("font-size: 11px; color: #adadc9; font-family: 'Inter';")
        portal_layout.addWidget(lbl_pc_desc)
        
        pc_visual = QHBoxLayout()
        self.portal_sphere = QLabel("🔮")
        self.portal_sphere.setStyleSheet("font-size: 26px; background-color: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 20px; padding: 8px;")
        
        pc_info = QVBoxLayout()
        pc_label = QLabel("Active Profile")
        pc_label.setStyleSheet("font-size: 9px; color: #7878a3; text-transform: uppercase; font-family: 'Outfit'; font-weight: bold;")
        self.lbl_portal_profile = QLabel("Rest Mode (Clean Workspace)")
        self.lbl_portal_profile.setWordWrap(True)
        self.lbl_portal_profile.setStyleSheet("font-size: 11px; font-weight: bold; color: #eaeaf2; font-family: 'Inter';")
        pc_info.addWidget(pc_label)
        pc_info.addWidget(self.lbl_portal_profile)
        
        pc_visual.addWidget(self.portal_sphere)
        pc_visual.addLayout(pc_info)
        portal_layout.addLayout(pc_visual)
        
        lbl_pc_tip = QLabel("Open VS Code to auto-load your Work Profile, or Steam to load your Recharge profile.")
        lbl_pc_tip.setWordWrap(True)
        lbl_pc_tip.setStyleSheet("font-size: 10px; color: #7878a3; line-height: 1.3; font-family: 'Inter';")
        portal_layout.addWidget(lbl_pc_tip)
        grid.addWidget(self.portal_card, 1, 0, 1, 1)
        
        # Widget 4: Quick Reflection Card
        self.reflect_card = QFrame()
        self.reflect_card.setProperty("class", "Card")
        apply_shadow_effect(self.reflect_card, "rgba(0, 0, 0, 0.3)", 20)
        
        reflect_layout = QVBoxLayout(self.reflect_card)
        reflect_layout.setContentsMargins(18, 18, 18, 18)
        reflect_layout.setSpacing(10)
        
        title_rc = QLabel("Quick Check-in")
        title_rc.setProperty("class", "card-title")
        reflect_layout.addWidget(title_rc)
        
        rc_desc = QLabel("How are you feeling? Logging roadblocks helps build the Energy Map.")
        rc_desc.setStyleSheet("font-size: 11px; color: #adadc9; font-family: 'Inter';")
        reflect_layout.addWidget(rc_desc)
        
        rc_grid = QGridLayout()
        rc_grid.setSpacing(10)
        
        lbl_er = QLabel("Mental Energy:")
        lbl_er.setStyleSheet("font-size: 10px; font-weight: bold; color: #adadc9; font-family: 'Outfit';")
        rc_grid.addWidget(lbl_er, 0, 0)
        
        energy_layout = QHBoxLayout()
        self.energy_buttons = []
        energy_data = [
            (1, "😰"), (2, "😮‍💨"), (3, "😐"), (4, "😊"), (5, "🔥")
        ]
        for val, emoji in energy_data:
            btn = QPushButton(emoji)
            btn.setCheckable(True)
            btn.setProperty("val", val)
            btn.setProperty("class", "rate-btn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(self.energy_btn_clicked)
            energy_layout.addWidget(btn)
            self.energy_buttons.append(btn)
        self.energy_buttons[4].setChecked(True)
        self.energy_buttons[4].setStyleSheet("background-color: rgba(45, 212, 168, 0.15); border: 1px solid #2dd4a8; color: #2dd4a8;")
        rc_grid.addLayout(energy_layout, 0, 1)
        
        lbl_fr = QLabel("Task Friction:")
        lbl_fr.setStyleSheet("font-size: 10px; font-weight: bold; color: #adadc9; font-family: 'Outfit';")
        rc_grid.addWidget(lbl_fr, 1, 0)
        
        friction_layout = QHBoxLayout()
        self.friction_buttons = []
        friction_data = [
            (1, "🌊"), (2, "🌤️"), (3, "⛅"), (4, "🌩️"), (5, "🧱")
        ]
        for val, emoji in friction_data:
            btn = QPushButton(emoji)
            btn.setCheckable(True)
            btn.setProperty("val", val)
            btn.setProperty("class", "rate-btn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(self.friction_btn_clicked)
            friction_layout.addWidget(btn)
            self.friction_buttons.append(btn)
        self.friction_buttons[1].setChecked(True)
        self.friction_buttons[1].setStyleSheet("background-color: rgba(180, 154, 255, 0.15); border: 1px solid #b49aff; color: #b49aff;")
        rc_grid.addLayout(friction_layout, 1, 1)
        
        reflect_layout.addLayout(rc_grid)
        
        lbl_ti = QLabel("Roadblock / Win Summary:")
        lbl_ti.setStyleSheet("font-size: 10px; font-weight: bold; color: #adadc9; font-family: 'Outfit';")
        reflect_layout.addWidget(lbl_ti)
        
        self.reflection_input = QLineEdit()
        self.reflection_input.setPlaceholderText("e.g. Fixed database lock crash! (Win)")
        reflect_layout.addWidget(self.reflection_input)
        
        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(6)
        tags = ["Coding Win", "Bug Roadblock", "Stuck in Loop", "Deep Flow", "Rest Break"]
        for t in tags:
            tbtn = QPushButton(f"+ {t}")
            tbtn.setCursor(Qt.PointingHandCursor)
            tbtn.setStyleSheet("background-color: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 4px; padding: 3px 6px; font-size: 9px; color: #adadc9; font-family: 'Inter';")
            tbtn.clicked.connect(lambda checked=False, val=t: self.add_reflection_tag(val))
            tags_layout.addWidget(tbtn)
        reflect_layout.addLayout(tags_layout)
        
        self.btn_submit_reflection = QPushButton("Save Reflection")
        self.btn_submit_reflection.setCursor(Qt.PointingHandCursor)
        self.btn_submit_reflection.setProperty("class", "action-btn")
        self.btn_submit_reflection.clicked.connect(self.save_reflection)
        reflect_layout.addWidget(self.btn_submit_reflection)
        
        grid.addWidget(self.reflect_card, 1, 1, 1, 2)
        page_layout.addLayout(grid)
        
        self.pages.addWidget(page)
        
    def energy_btn_clicked(self):
        sender = self.sender()
        self.selected_energy = sender.property("val")
        for btn in self.energy_buttons:
            if btn == sender:
                btn.setChecked(True)
                btn.setStyleSheet("background-color: rgba(45, 212, 168, 0.15); border: 1px solid #2dd4a8; color: #2dd4a8;")
            else:
                btn.setChecked(False)
                btn.setStyleSheet("")
                
    def friction_btn_clicked(self):
        sender = self.sender()
        self.selected_friction = sender.property("val")
        for btn in self.friction_buttons:
            if btn == sender:
                btn.setChecked(True)
                btn.setStyleSheet("background-color: rgba(180, 154, 255, 0.15); border: 1px solid #b49aff; color: #b49aff;")
            else:
                btn.setChecked(False)
                btn.setStyleSheet("")
                
    def add_reflection_tag(self, tag):
        current = self.reflection_input.text().strip()
        tag_str = f"[{tag}]"
        if not current:
            self.reflection_input.setText(f"{tag_str} ")
        else:
            if tag_str not in current:
                self.reflection_input.setText(f"{tag_str} {current}")
        self.reflection_input.setFocus()
        
    def save_reflection(self):
        summary = self.reflection_input.text().strip()
        if not summary:
            self.reflection_input.setStyleSheet("border: 1px solid #ff6b6b;")
            return
        
        self.reflection_input.setStyleSheet("")
        db.add_reflection(self.selected_energy, self.selected_friction, summary)
        self.reflection_input.clear()
        self.poll_shared_state()
        
        self.banner_text.setText("✓ Reflection logged inside local database. Battery updated.")
        self.banner.setStyleSheet("background-color: rgba(45, 212, 168, 0.05); border: 1px solid rgba(45, 212, 168, 0.2); border-radius: 12px; padding: 12px;")
        QTimer.singleShot(4000, lambda: self.reset_banner_toast())

    def reset_banner_toast(self):
        self.banner.setStyleSheet("background-color: rgba(180, 154, 255, 0.04); border: 1px solid rgba(180, 154, 255, 0.15); border-radius: 12px; padding: 12px;")
        self.banner_text.setText("Your companion is watching over you. Looking good!")

    def quick_add_keyword(self, mode):
        if not shared_state["last_external_window"] or shared_state["last_external_window"] == "None":
            return
        
        title = shared_state["last_external_window"]
        proc = shared_state["last_external_process"]
        
        browser_processes = ["chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe", "iexplore.exe"]
        is_browser = proc.lower() in browser_processes
        
        if is_browser:
            raw_keyword = title.strip()
            separators = raw_keyword.split(" - ")
            if len(separators) > 1:
                extracted = separators[0].strip().lower()
            else:
                extracted = raw_keyword.lower()
        else:
            extracted = proc.lower()
            
        if not extracted:
            return
            
        settings = db.get_settings()
        key = "work_keywords" if mode == "work" else "recharge_keywords"
        current_list = settings.get(key, [])
        
        if extracted not in current_list:
            current_list.append(extracted)
            settings[key] = current_list
            db.update_settings(settings)
            self.banner_text.setText(f"✓ Added '{extracted}' to {mode} keywords!")
            self.banner.setStyleSheet("background-color: rgba(45, 212, 168, 0.05); border: 1px solid rgba(45, 212, 168, 0.2); border-radius: 12px; padding: 12px;")
            QTimer.singleShot(4000, lambda: self.reset_banner_toast())
            self.poll_shared_state()

    # ----------------- TAB 2: ENERGY MAP & LOGS -----------------
    def build_analytics_tab(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(20)
        
        # Header
        title_box = QVBoxLayout()
        header_title = QLabel("Your Energy Map")
        header_title.setStyleSheet("font-family: 'Outfit'; font-size: 24px; font-weight: bold; color: #eaeaf2;")
        header_sub = QLabel("See how your energy and focus patterns evolve throughout the week.")
        header_sub.setStyleSheet("font-size: 13px; color: #adadc9; font-family: 'Inter';")
        title_box.addWidget(header_title)
        title_box.addWidget(header_sub)
        page_layout.addLayout(title_box)
        
        layout_grid = QGridLayout()
        layout_grid.setSpacing(20)
        
        # Custom Anti-aliased QPainter Chart Card
        chart_card = QFrame()
        chart_card.setProperty("class", "Card")
        apply_shadow_effect(chart_card, "rgba(0, 0, 0, 0.3)", 20)
        
        chart_card_layout = QVBoxLayout(chart_card)
        chart_card_layout.setContentsMargins(15, 15, 15, 15)
        
        lbl_cc = QLabel("Weekly Fatigue & Friction Analysis")
        lbl_cc.setProperty("class", "card-title")
        lbl_cc_desc = QLabel("Comparison of task friction against mental energy levels throughout the week.")
        lbl_cc_desc.setProperty("class", "card-desc")
        
        self.custom_chart = EnergyChart()
        
        legend_layout = QHBoxLayout()
        legend_layout.setAlignment(Qt.AlignCenter)
        legend_layout.setSpacing(20)
        
        item1 = QHBoxLayout()
        col1 = QLabel("●")
        col1.setStyleSheet("color: #2dd4a8; font-size: 16px;")
        lbl1 = QLabel("Mental Energy (Higher is Better)")
        lbl1.setStyleSheet("font-size: 11px; color: #adadc9; font-family: 'Inter';")
        item1.addWidget(col1)
        item1.addWidget(lbl1)
        
        item2 = QHBoxLayout()
        col2 = QLabel("●")
        col2.setStyleSheet("color: #b49aff; font-size: 16px;")
        lbl2 = QLabel("Task Friction Level (Lower is Better)")
        lbl2.setStyleSheet("font-size: 11px; color: #adadc9; font-family: 'Inter';")
        item2.addWidget(col2)
        item2.addWidget(lbl2)
        
        legend_layout.addLayout(item1)
        legend_layout.addLayout(item2)
        
        chart_card_layout.addWidget(lbl_cc)
        chart_card_layout.addWidget(lbl_cc_desc)
        chart_card_layout.addWidget(self.custom_chart)
        chart_card_layout.addLayout(legend_layout)
        
        layout_grid.addWidget(chart_card, 0, 0, 1, 3)
        
        # Bottom Left: Wellbeing Insights Scroll area
        insights_card = QFrame()
        insights_card.setProperty("class", "Card")
        apply_shadow_effect(insights_card, "rgba(0, 0, 0, 0.3)", 20)
        
        insights_layout_outer = QVBoxLayout(insights_card)
        insights_layout_outer.setContentsMargins(15, 15, 15, 15)
        
        lbl_ic = QLabel("Wellbeing Insights")
        lbl_ic.setProperty("class", "card-title")
        insights_layout_outer.addWidget(lbl_ic)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        self.insights_layout = QVBoxLayout(scroll_content)
        self.insights_layout.setSpacing(12)
        self.insights_layout.setContentsMargins(0, 0, 10, 0)
        self.insights_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        insights_layout_outer.addWidget(scroll)
        
        layout_grid.addWidget(insights_card, 1, 0, 1, 1)
        
        # Bottom Right: Table Logs Card
        logs_card = QFrame()
        logs_card.setProperty("class", "Card")
        apply_shadow_effect(logs_card, "rgba(0, 0, 0, 0.3)", 20)
        
        logs_layout = QVBoxLayout(logs_card)
        logs_layout.setContentsMargins(15, 15, 15, 15)
        
        lbl_lc = QLabel("Reflection Logs")
        lbl_lc.setProperty("class", "card-title")
        logs_layout.addWidget(lbl_lc)
        
        self.logs_table = QTableWidget()
        self.logs_table.setColumnCount(4)
        self.logs_table.setHorizontalHeaderLabels(["Date", "Energy", "Friction", "ROADBLOCK / WIN Summary"])
        
        header = self.logs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        
        logs_layout.addWidget(self.logs_table)
        
        layout_grid.addWidget(logs_card, 1, 1, 1, 2)
        page_layout.addLayout(layout_grid)
        
        self.pages.addWidget(page)
        
    def load_analytics_data(self):
        reflections = db.get_reflections()
        sessions = db.get_sessions()
        
        weekday_data = {i: {"energy": [], "friction": [], "count": 0} for i in range(7)}
        for r in reflections:
            try:
                dt = datetime.fromisoformat(r["timestamp"])
                w = dt.weekday()
                weekday_data[w]["energy"].append(r["energy_level"])
                weekday_data[w]["friction"].append(r["friction_level"])
                weekday_data[w]["count"] += 1
            except Exception:
                pass
                
        weekday_summary = []
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for w in range(7):
            energy_avg = sum(weekday_data[w]["energy"]) / len(weekday_data[w]["energy"]) if weekday_data[w]["energy"] else 0
            friction_avg = sum(weekday_data[w]["friction"]) / len(weekday_data[w]["friction"]) if weekday_data[w]["friction"] else 0
            weekday_summary.append({
                "day": days[w],
                "avg_energy": round(energy_avg, 2),
                "avg_friction": round(friction_avg, 2),
                "count": weekday_data[w]["count"]
            })
            
        self.custom_chart.setData(weekday_summary)
        
        # Calculate dynamic insights
        insights = []
        total_work = 0
        total_rest_recharge = 0
        bypassed_count = 0
        for s in sessions:
            mode = s.get("mode")
            duration = s.get("duration", 0)
            if mode == "work":
                total_work += duration
            elif mode in ["recharge", "rest"]:
                total_rest_recharge += duration
            if s.get("bypassed", False):
                bypassed_count += 1
                
        if total_work > 0:
            ratio = total_work / (total_rest_recharge + 1)
            if ratio > 4.5:
                insights.append({
                    "id": "focus_ratio", "title": "Burnout Susceptibility", "type": "danger", "icon": "🚨",
                    "metric": f"{ratio:.1f}:1 Ratio",
                    "description": "Your focused work time is extremely high compared to your rest/recovery periods. Working in prolonged blocks without breaks leads to mental fatigue, cognitive bottlenecks, and slower problem-solving.",
                    "actionable_tip": "Shorten your work blocks to 25-30 minutes and force a 5-minute physical break away from the screen."
                })
            elif 2.0 <= ratio <= 4.5:
                insights.append({
                    "id": "focus_ratio", "title": "Focus Balance", "type": "success", "icon": "⚖️",
                    "metric": f"{ratio:.1f}:1 Ratio",
                    "description": "Excellent! Your focus-to-rest ratio is in the optimal performance zone. This sustainable pace prevents mental burnout while maintaining strong daily progress.",
                    "actionable_tip": "Maintain this cadence. Tag your reflections to lock in what keeps you in this balanced flow."
                })
            else:
                insights.append({
                    "id": "focus_ratio", "title": "Cognitive Recovery", "type": "info", "icon": "🔋",
                    "metric": f"{ratio:.1f}:1 Ratio",
                    "description": "You are spending a significant portion of your time resting and recharging. This is excellent for deep fatigue recovery, but ensure your focus blocks are highly focused.",
                    "actionable_tip": "When you start a focus block, hide distractions and let MIND-FLOW clean your workspace automatically."
                })
                
        if bypassed_count > 0:
            insights.append({
                "id": "bypassed_breaks", "title": "Break Compliance", "type": "warning", "icon": "⚠️",
                "metric": f"{bypassed_count} Skipped",
                "description": f"You have bypassed {bypassed_count} visual shield lockout breaks. Skipping eye strain breaks diminishes focus quality and increases neural fatigue over time.",
                "actionable_tip": "When the lockout activates, look at an object 20 feet away for 20 seconds. It is a quick recharge that preserves your long-term focus."
            })
        elif total_work > 0:
            insights.append({
                "id": "bypassed_breaks", "title": "Break Discipline", "type": "success", "icon": "🛡️",
                "metric": "100% Guarded",
                "description": "Perfect score! You have respected every visual shield lockout break. Your focus blocks are safely buffered, preventing eye strain and cognitive decline.",
                "actionable_tip": "Keep it up. Regular micro-breaks keep your brain primed for complex debugging tasks."
            })
            
        high_friction_reflections = [r for r in reflections if r["friction_level"] >= 4]
        if high_friction_reflections:
            recent_refl = high_friction_reflections[-1]
            insights.append({
                "id": "friction_hotspot", "title": "Friction Hotspot", "type": "warning", "icon": "🚧",
                "metric": f"{len(high_friction_reflections)} Alerts",
                "description": f"High task friction detected in recent focus sessions. Your latest obstacle was: '{recent_refl.get('summary', '')}'. High friction points to structural roadblocks or mental fatigue.",
                "actionable_tip": "Divide your current complex task into small sub-tasks. Check in with tags like 'Coding Win' to boost motivation."
            })
        elif reflections:
            insights.append({
                "id": "friction_hotspot", "title": "Friction Status", "type": "success", "icon": "🌊",
                "metric": "Low Friction",
                "description": "Your tasks are progressing smoothly with minimal mental roadblocks. You are in a clear cognitive state.",
                "actionable_tip": "This is the best time to tackle your most complex architectural designs or key features."
            })
            
        self.populate_insights(insights)
        self.populate_logs(reflections)
        
    def populate_insights(self, insights):
        # Clear layout
        while self.insights_layout.count() > 1:
            item = self.insights_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        if not insights:
            lbl = QLabel("Your routine looks balanced! Keep tracking focus windows to compile insights.")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #adadc9; font-size: 11px; font-style: italic; font-family: 'Inter';")
            self.insights_layout.insertWidget(0, lbl)
            return
            
        for ins in reversed(insights):
            frame = QFrame()
            
            t = ins.get("type", "info")
            if t == "danger":
                color, bg = "#ff6b6b", "rgba(255, 107, 107, 0.02)"
            elif t == "warning":
                color, bg = "#fbbf24", "rgba(251, 191, 36, 0.02)"
            elif t == "success":
                color, bg = "#2dd4a8", "rgba(45, 212, 168, 0.02)"
            else:
                color, bg = "#b49aff", "rgba(180, 154, 255, 0.02)"
                
            frame.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {bg}, stop:1 rgba(255,255,255,0.01));
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-left: 4px solid {color};
                    border-radius: 12px;
                }}
            """)
            
            flayout = QVBoxLayout(frame)
            flayout.setSpacing(6)
            flayout.setContentsMargins(12, 12, 12, 12)
            
            h = QHBoxLayout()
            title = QLabel(f"{ins['icon']}  {ins['title']}")
            title.setStyleSheet("font-weight: bold; color: #eaeaf2; font-size: 12px; font-family: 'Outfit';")
            metric = QLabel(ins["metric"])
            metric.setStyleSheet(f"font-weight: bold; color: {color}; border: 1px solid {color}; border-radius: 4px; padding: 1px 5px; font-size: 9px; font-family: 'Inter';")
            h.addWidget(title)
            h.addStretch()
            h.addWidget(metric)
            flayout.addLayout(h)
            
            desc = QLabel(ins["description"])
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #adadc9; font-size: 11px; line-height: 1.4; font-family: 'Inter';")
            flayout.addWidget(desc)
            
            tip = QLabel(f"<b>Action Tip:</b> {ins['actionable_tip']}")
            tip.setWordWrap(True)
            tip.setStyleSheet("color: #7878a3; font-size: 10px; background-color: rgba(0, 0, 0, 0.15); padding: 5px; border-radius: 4px; font-family: 'Inter';")
            flayout.addWidget(tip)
            
            self.insights_layout.insertWidget(0, frame)
            
    def populate_logs(self, reflections):
        self.logs_table.setRowCount(0)
        sorted_reflections = list(reversed(reflections))[-15:]
        self.logs_table.setRowCount(len(sorted_reflections))
        
        for row, ref in enumerate(sorted_reflections):
            try:
                dt = datetime.fromisoformat(ref["timestamp"])
                dt_str = dt.strftime("%m-%d %H:%M")
            except:
                dt_str = ref["timestamp"]
                
            e_level = ref["energy_level"]
            f_level = ref["friction_level"]
            summary = ref["summary"]
            
            item_date = QTableWidgetItem(dt_str)
            item_energy = QTableWidgetItem(f"{e_level} / 5")
            if e_level <= 2:
                item_energy.setForeground(QColor("#ff6b6b"))
            else:
                item_energy.setForeground(QColor("#2dd4a8"))
                
            item_friction = QTableWidgetItem(f"{f_level} / 5")
            if f_level >= 4:
                item_friction.setForeground(QColor("#ff6b6b"))
            else:
                item_friction.setForeground(QColor("#b49aff"))
                
            item_summary = QTableWidgetItem(summary)
            
            item_date.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_energy.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            item_friction.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            item_summary.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            
            self.logs_table.setItem(row, 0, item_date)
            self.logs_table.setItem(row, 1, item_energy)
            self.logs_table.setItem(row, 2, item_friction)
            self.logs_table.setItem(row, 3, item_summary)

    # ----------------- TAB 3: PREFERENCES -----------------
    def build_settings_tab(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(20)
        
        # Header
        title_box = QVBoxLayout()
        header_title = QLabel("Your Preferences")
        header_title.setStyleSheet("font-family: 'Outfit'; font-size: 24px; font-weight: bold; color: #eaeaf2;")
        header_sub = QLabel("Customize how your companion monitors focus windows and manages breaks.")
        header_sub.setStyleSheet("font-size: 13px; color: #adadc9; font-family: 'Inter';")
        title_box.addWidget(header_title)
        title_box.addWidget(header_sub)
        page_layout.addLayout(title_box)
        
        # Settings Card Form
        settings_card = QFrame()
        settings_card.setProperty("class", "Card")
        apply_shadow_effect(settings_card, "rgba(0, 0, 0, 0.3)", 20)
        settings_card.setMaximumWidth(750)
        sc_layout = QVBoxLayout(settings_card)
        sc_layout.setContentsMargins(20, 20, 20, 20)
        sc_layout.setSpacing(15)
        
        lbl_s_title = QLabel("Focus & Recharge Parameters")
        lbl_s_title.setProperty("class", "card-title")
        sc_layout.addWidget(lbl_s_title)
        
        grid_form = QGridLayout()
        grid_form.setSpacing(15)
        
        lbl_w_lim = QLabel("Work Block Limit (Minutes):")
        lbl_w_lim.setStyleSheet("font-size: 11px; font-weight: bold; color: #eaeaf2; font-family: 'Outfit';")
        self.spin_work_limit = QLineEdit()
        self.spin_work_limit.setPlaceholderText("45")
        grid_form.addWidget(lbl_w_lim, 0, 0)
        grid_form.addWidget(self.spin_work_limit, 0, 1)
        
        lbl_i_lim = QLabel("Idle Sensing Timeout (Seconds):")
        lbl_i_lim.setStyleSheet("font-size: 11px; font-weight: bold; color: #eaeaf2; font-family: 'Outfit';")
        self.spin_idle_limit = QLineEdit()
        self.spin_idle_limit.setPlaceholderText("180")
        grid_form.addWidget(lbl_i_lim, 1, 0)
        grid_form.addWidget(self.spin_idle_limit, 1, 1)
        
        sc_layout.addLayout(grid_form)
        
        self.cb_autopilot = QCheckBox("Enable Cognitive Autopilot (Adaptive Sprints)")
        self.cb_autopilot.setStyleSheet("QCheckBox { font-size: 11px; font-weight: bold; color: #eaeaf2; font-family: 'Outfit'; } QCheckBox::indicator { width: 16px; height: 16px; }")
        sc_layout.addWidget(self.cb_autopilot)
        
        lbl_ap_desc = QLabel("Dynamically scale work and rest limits based on reflection ratings and bypassed rest breaks.")
        lbl_ap_desc.setStyleSheet("font-size: 10px; color: #7878a3; margin-top: -10px; font-family: 'Inter';")
        sc_layout.addWidget(lbl_ap_desc)
        
        lbl_work_kws = QLabel("Work Mode Window Title Keywords:")
        lbl_work_kws.setStyleSheet("font-size: 11px; font-weight: bold; color: #eaeaf2; font-family: 'Outfit';")
        self.txt_work_kws = QTextEdit()
        self.txt_work_kws.setPlaceholderText("e.g. vs code, visual studio, word, docs")
        self.txt_work_kws.setMaximumHeight(80)
        sc_layout.addWidget(lbl_work_kws)
        sc_layout.addWidget(self.txt_work_kws)
        
        lbl_recharge_kws = QLabel("Recharge Mode Window Title Keywords:")
        lbl_recharge_kws.setStyleSheet("font-size: 11px; font-weight: bold; color: #eaeaf2; font-family: 'Outfit';")
        self.txt_recharge_kws = QTextEdit()
        self.txt_recharge_kws.setPlaceholderText("e.g. steam, vlc, netflix, youtube, spotify")
        self.txt_recharge_kws.setMaximumHeight(80)
        sc_layout.addWidget(lbl_recharge_kws)
        sc_layout.addWidget(self.txt_recharge_kws)
        
        apply_layout = QHBoxLayout()
        self.lbl_settings_status = QLabel("")
        self.lbl_settings_status.setStyleSheet("font-size: 11px; color: #2dd4a8; font-family: 'Inter';")
        btn_save_settings = QPushButton("Apply Settings")
        btn_save_settings.setCursor(Qt.PointingHandCursor)
        btn_save_settings.setProperty("class", "action-btn")
        btn_save_settings.clicked.connect(self.save_settings_data)
        
        apply_layout.addWidget(self.lbl_settings_status)
        apply_layout.addStretch()
        apply_layout.addWidget(btn_save_settings)
        sc_layout.addLayout(apply_layout)
        
        page_layout.addWidget(settings_card)
        page_layout.addStretch()
        self.pages.addWidget(page)
        
    def load_settings_data(self):
        settings = db.get_settings()
        self.spin_work_limit.setText(str(settings.get("work_duration_minutes", 45)))
        self.spin_idle_limit.setText(str(settings.get("idle_timeout_seconds", 180)))
        self.cb_autopilot.setChecked(settings.get("adaptive_timers_enabled", True))
        
        self.txt_work_kws.setText(", ".join(settings.get("work_keywords", [])))
        self.txt_recharge_kws.setText(", ".join(settings.get("recharge_keywords", [])))
        
    def save_settings_data(self):
        try:
            work_mins = int(self.spin_work_limit.text())
            idle_sec = int(self.spin_idle_limit.text())
        except ValueError:
            self.lbl_settings_status.setStyleSheet("color: #ff6b6b;")
            self.lbl_settings_status.setText("Error: Limit fields must be numbers!")
            return
            
        settings = {
            "work_duration_minutes": work_mins,
            "idle_timeout_seconds": idle_sec,
            "adaptive_timers_enabled": self.cb_autopilot.isChecked(),
            "work_keywords": [k.strip() for k in self.txt_work_kws.toPlainText().split(",") if k.strip()],
            "recharge_keywords": [k.strip() for k in self.txt_recharge_kws.toPlainText().split(",") if k.strip()]
        }
        db.update_settings(settings)
        self.lbl_settings_status.setStyleSheet("color: #2dd4a8;")
        self.lbl_settings_status.setText("✓ Settings saved successfully!")
        QTimer.singleShot(3000, lambda: self.lbl_settings_status.setText(""))
        
    # ----------------- GUI SYNCHRONIZATION TIMER -----------------
    def poll_shared_state(self):
        now = datetime.now()
        self.lbl_clock.setText(now.strftime("%I:%M %p"))
        
        mode = shared_state["current_mode"]
        self.lbl_shield_mode.setText(f"{mode.capitalize()} Mode")
        
        # Map rotating shield properties
        emoji = "⚪"
        if mode == "work":
            emoji = "💻"
            self.lbl_block_timer.setStyleSheet("font-family: 'Outfit'; font-size: 20px; font-weight: bold; color: #b49aff;")
            self.lbl_portal_profile.setText("Work Mode (Work Files Active)")
            self.portal_sphere.setText("🔮")
        elif mode == "recharge":
            emoji = "🎮"
            self.lbl_block_timer.setStyleSheet("font-family: 'Outfit'; font-size: 20px; font-weight: bold; color: #2dd4a8;")
            self.lbl_portal_profile.setText("Recharge Mode (Games Active)")
            self.portal_sphere.setText("🌌")
        elif mode == "rest":
            emoji = "💤"
            self.lbl_block_timer.setStyleSheet("font-family: 'Outfit'; font-size: 20px; font-weight: bold; color: #fbbf24;")
            self.lbl_portal_profile.setText("Rest Mode (Workspace Hidden)")
            self.portal_sphere.setText("⚪")
        else:
            self.lbl_block_timer.setStyleSheet("font-family: 'Outfit'; font-size: 20px; font-weight: bold; color: #7878a3;")
            self.lbl_portal_profile.setText("Neutral (Normal Desktop)")
            self.portal_sphere.setText("⚪")
            
        self.shield_ring.setMode(mode, emoji)
        
        # Countdown
        adaptive = db.get_adaptive_times()
        work_limit_seconds = adaptive["work_minutes"] * 60
        elapsed = shared_state["elapsed_seconds"]
        self.lbl_shield_badge.setText(adaptive["reason"])
        
        if mode == "work":
            remaining = max(0, work_limit_seconds - elapsed)
            mins = remaining // 60
            secs = remaining % 60
            self.lbl_block_timer.setText(f"{mins:02d}:{secs:02d}")
            if remaining < 60:
                self.lbl_block_timer.setStyleSheet("font-family: 'Outfit'; font-size: 20px; font-weight: bold; color: #ff6b6b;")
        elif mode == "recharge":
            mins = elapsed // 60
            secs = elapsed % 60
            self.lbl_block_timer.setText(f"{mins:02d}:{secs:02d}")
        elif mode == "rest":
            idle = shared_state["idle_seconds"]
            mins = idle // 60
            secs = idle % 60
            self.lbl_block_timer.setText(f"{mins:02d}:{secs:02d}")
        else:
            self.lbl_block_timer.setText("00:00")
            
        app_name = shared_state["active_window_title"]
        proc_name = shared_state["active_process_name"]
        self.lbl_foreground_app.setText(app_name if len(app_name) <= 30 else app_name[:27] + "...")
        self.lbl_foreground_process.setText(f"Process: {proc_name}" if len(proc_name) <= 40 else f"Process: {proc_name[:37]}...")
        
        # Battery calculations
        reflections = db.get_reflections()
        today_str = date.today().isoformat()
        today_reflections = [r for r in reflections if r["timestamp"].startswith(today_str)]
        
        current_energy = 5
        if today_reflections:
            current_energy = today_reflections[-1]["energy_level"]
            
        pct = current_energy * 20
        self.battery_bar.setValue(pct)
        self.lbl_battery_pct.setText(f"{pct}%")
        
        if current_energy <= 2:
            color = "#ff6b6b"
            self.lbl_battery_msg.setText("You're running low. Time for a gentle break to recharge.")
            self.lbl_battery_msg.setStyleSheet("font-size: 11px; color: #ff6b6b; font-family: 'Inter';")
            # Apply dynamic red glow when battery is low
            apply_shadow_effect(self.battery_card, "rgba(255, 107, 107, 0.15)", 20)
        elif current_energy == 3:
            color = "#f59e0b"
            self.lbl_battery_msg.setText("Moderate energy. A short break soon would feel nice.")
            self.lbl_battery_msg.setStyleSheet("font-size: 11px; color: #f59e0b; font-family: 'Inter';")
            apply_shadow_effect(self.battery_card, "rgba(245, 158, 11, 0.15)", 20)
        else:
            color = "#2dd4a8"
            self.lbl_battery_msg.setText("Feeling great! Keep going, and remember to rest when needed.")
            self.lbl_battery_msg.setStyleSheet("font-size: 11px; color: #adadc9; font-family: 'Inter';")
            # Default premium soft shadow
            apply_shadow_effect(self.battery_card, "rgba(0, 0, 0, 0.3)", 20)
            
        self.battery_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                background-color: rgba(0, 0, 0, 0.2);
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)
        
        if mode == "work":
            self.lbl_battery_state.setText("❌ discharging")
            self.lbl_battery_state.setStyleSheet("font-size: 11px; color: #ff6b6b; font-weight: bold; font-family: 'Outfit';")
        elif mode in ["recharge", "rest"]:
            self.lbl_battery_state.setText("⚡ charging")
            self.lbl_battery_state.setStyleSheet("font-size: 11px; color: #2dd4a8; font-weight: bold; font-family: 'Outfit';")
        else:
            self.lbl_battery_state.setText("⏳ holding")
            self.lbl_battery_state.setStyleSheet("font-size: 11px; color: #7878a3; font-weight: bold; font-family: 'Outfit';")

        # Session Durations
        sessions = db.get_sessions()
        today_work, today_recharge, today_rest = 0, 0, 0
        today_bypasses = 0
        
        for s in sessions:
            if s["start"].startswith(today_str):
                m = s["mode"]
                dur = s["duration"]
                if m == "work":
                    today_work += dur
                elif m == "recharge":
                    today_recharge += dur
                elif m == "rest":
                    today_rest += dur
                if s.get("bypassed", False):
                    today_bypasses += 1
                    
        if mode == "work":
            today_work += elapsed
        elif mode == "recharge":
            today_recharge += elapsed
        elif mode == "rest":
            today_rest += shared_state["idle_seconds"]
            
        def format_dur(sec):
            h = int(sec) // 3600
            m = (int(sec) % 3600) // 60
            return f"{h}h {m}m"
            
        self.lbl_stat_work.setText(format_dur(today_work))
        self.lbl_stat_recharge.setText(format_dur(today_recharge))
        self.lbl_stat_rest.setText(format_dur(today_rest))
        
        # Dynamic Advice Banner
        advice = "Your cognitive shield is active. Looking good!"
        if not shared_state["tracking_active"]:
            advice = "Companion is paused. Take care of yourself out there!"
        elif today_bypasses > 1:
            advice = f"That's {today_bypasses} breaks skipped today. Your code can wait; your health shouldn't."
        elif today_bypasses == 1:
            advice = "I noticed you skipped a break earlier. Let's try to take the next 20-second pause together."
        elif current_energy <= 2:
            advice = "Battery critical! Focus blocks are blocked. Please start your recharge/rest."
        elif current_energy == 3:
            advice = "Medium energy. Be careful not to push yourself into a hyperfocus trap."
        elif mode == "work":
            advice = "Deep work block active. Stay focused, but don't ignore the warning beeps."
        elif mode == "recharge":
            advice = "Recharging active. Enjoy the break and clear your head!"
        elif mode == "rest":
            advice = "Rest block. Remember to look 20 feet away to relax your eyes."
        
        if self.banner_text.text() not in ["✓ Settings saved successfully!", "Your companion is watching over you. Looking good!"] and not self.banner_text.text().startswith("✓"):
            pass
        else:
            if self.banner_text.text().startswith("✓"):
                pass
            else:
                self.banner_text.setText(advice)
                
        if shared_state["tracking_active"]:
            self.lbl_tracking_status.setText("Shield Active")
            self.lbl_tracking_status.setStyleSheet("font-size: 11px; color: #2dd4a8; font-weight: bold; font-family: 'Outfit';")
            self.btn_toggle_tracking.setText("Pause Companion")
        else:
            self.lbl_tracking_status.setText("Companion Paused")
            self.lbl_tracking_status.setStyleSheet("font-size: 11px; color: #ff6b6b; font-weight: bold; font-family: 'Outfit';")
            self.btn_toggle_tracking.setText("Resume Companion")

    def toggle_tracking(self):
        shared_state["tracking_active"] = not shared_state["tracking_active"]
        self.poll_shared_state()
        
    def closeEvent(self, event):
        print("MIND-FLOW Native close event triggered. Tidying workspace...")
        from backend.workspace import WorkspaceManager
        workspace = WorkspaceManager()
        cur_mode = shared_state["current_mode"]
        db.log_session(cur_mode, datetime.now(), datetime.now())
        workspace.swap_workspace(cur_mode, "neutral")
        event.accept()
        os._exit(0)

if __name__ == "__main__":
    os.makedirs(r"C:\MIND\Workspace_Profiles\Work", exist_ok=True)
    os.makedirs(r"C:\MIND\Workspace_Profiles\Recharge", exist_ok=True)
    
    # 1. Spawn native PyQt window (instant start)
    qt_app = QApplication(sys.argv)
    qt_app.setStyleSheet(QSS_STYLE)
    
    # 2. Load application fonts dynamically (requires QApplication initialization)
    load_fonts()
    
    # 3. Start the watcher background thread
    watcher_thread = threading.Thread(target=main_state_machine, daemon=True)
    watcher_thread.start()
    
    window = MainWindow()
    window.show()
    
    sys.exit(qt_app.exec())
