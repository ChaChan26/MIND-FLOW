import os
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

def get_default_data_dir():
    legacy_dir = r"C:\MIND"
    if os.path.exists(legacy_dir) and os.path.isdir(legacy_dir):
        return legacy_dir
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if appdata:
            return os.path.join(appdata, "MIND")
    home = os.path.expanduser("~")
    return os.path.join(home, ".mindflow")

# Redirect standard logs for PyInstaller executable runs
if getattr(sys, 'frozen', False):
    is_gui = "--gui" in sys.argv
    log_suffix = "_gui" if is_gui else ""
    try:
        data_dir = get_default_data_dir()
        os.makedirs(data_dir, exist_ok=True)
        sys.stdout = Unbuffered(open(os.path.join(data_dir, f"app{log_suffix}_stdout.log"), "w", encoding="utf-8"))
        sys.stderr = Unbuffered(open(os.path.join(data_dir, f"app{log_suffix}_stderr.log"), "w", encoding="utf-8"))
    except Exception:
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

import time
import random
import math
import ctypes
import socket
import threading
import tkinter as tk
import winsound
from datetime import datetime, date

# Initialize and import backend components
from backend.database import MindFlowDB
db = MindFlowDB()

PHYSICAL_STRETCHES = [
    "Roll your shoulders backward in a slow circle 5 times.",
    "Gently tilt your head left for 5 seconds, then right for 5 seconds.",
    "Clasp your hands behind your back and push chest forward to stretch shoulders.",
    "Extend your arms forward, link fingers, and stretch your upper back.",
    "Close your eyes, cup your hands over them, and take 3 slow breaths in darkness.",
    "Rotate your wrists in slow circles outward, then inward 5 times."
]

EYE_EXERCISES = [
    "Look at the moving balloon and track it slowly with your eyes only, keeping your head still.",
    "Look at an object at least 20 feet away for 20 seconds, then focus on your finger nearby.",
    "Blink rapidly 10 times to naturally re-moisturize your eyes.",
    "Slowly roll your eyes in a circle clockwise, then counter-clockwise.",
    "Focus on a distant wall, and draw a giant figure-eight with your eyes.",
    "Rub your hands together to warm them, cup them over closed eyes, and rest for 10 seconds."
]

from backend.database import matches_keyword

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
        millis = (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF
        return max(0.0, millis / 1000.0)
    except Exception as e:
        print(f"Error reading idle seconds: {e}")
        return 0

def play_beep_sequence(sequence):
    """Play a sequence of beeps asynchronously, trying system sound first, falling back to Beep. Safe for unit tests."""
    def run():
        # Skip playing actual Windows audio events if running unit tests to avoid noise and test runner errors
        if os.environ.get("MINDFLOW_DB_FILE") == ":memory:":
            for freq, duration in sequence:
                try:
                    winsound.Beep(freq, duration)
                except Exception:
                    pass
            return

        try:
            if len(sequence) == 5:
                # Lockout start arpeggio equivalent: SystemNotification
                winsound.PlaySound("SystemNotification", winsound.SND_ALIAS)
            elif len(sequence) == 3:
                # Lockout end arpeggio equivalent: SystemAsterisk
                winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
            else:
                # Other transitions
                winsound.PlaySound("SystemDefault", winsound.SND_ALIAS)
        except Exception:
            for freq, duration in sequence:
                try:
                    winsound.Beep(freq, duration)
                except Exception:
                    pass
    threading.Thread(target=run, daemon=True).start()

# Win32 API Constants and Structures for Power Throttling (EcoQoS/Efficiency Mode)
ProcessPowerThrottling = 4
PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1

class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
    _fields_ = [
        ("Version", ctypes.c_ulong),
        ("ControlMask", ctypes.c_ulong),
        ("StateMask", ctypes.c_ulong),
    ]

def disable_ecoqos_for_handle(handle):
    """Disable EcoQoS (Power Throttling) for a given process handle to prevent CPU throttling on low clock."""
    try:
        state = PROCESS_POWER_THROTTLING_STATE()
        state.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION
        state.ControlMask = PROCESS_POWER_THROTTLING_EXECUTION_SPEED
        state.StateMask = 0  # 0 to disable throttling
        
        result = ctypes.windll.kernel32.SetProcessInformation(
            handle,
            ProcessPowerThrottling,
            ctypes.byref(state),
            ctypes.sizeof(state)
        )
        return bool(result)
    except Exception:
        return False

def is_gui_minimized():
    """Detect if the standalone MIND-FLOW pywebview window is minimized."""
    if sys.platform != "win32":
        return False
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, "MIND-FLOW // Cognitive Companion Dashboard")
        if hwnd:
            return bool(ctypes.windll.user32.IsIconic(hwnd))
    except Exception:
        pass
    return False

_parent_process_cache = None
_disabled_ecoqos_pids = set()

def disable_ecoqos_for_process_tree():
    """Disable EcoQoS recursively for current process and all child processes (like WebView2 renderers)."""
    global _parent_process_cache, _disabled_ecoqos_pids
    if sys.platform != "win32":
        return
    if is_gui_minimized():
        return
    try:
        import psutil
        PROCESS_SET_INFORMATION = 0x0200
        
        # 1. Disable for current process
        current_pid = os.getpid()
        if current_pid not in _disabled_ecoqos_pids:
            current_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_SET_INFORMATION, False, current_pid)
            if current_handle:
                try:
                    if disable_ecoqos_for_handle(current_handle):
                        _disabled_ecoqos_pids.add(current_pid)
                except Exception:
                    pass
                finally:
                    ctypes.windll.kernel32.CloseHandle(current_handle)
        
        # 2. Disable for all child/descendant processes recursively
        if _parent_process_cache is None:
            _parent_process_cache = psutil.Process()
            
        active_pids = {current_pid}
        try:
            children = _parent_process_cache.children(recursive=True)
        except Exception:
            children = []
            
        for child in children:
            active_pids.add(child.pid)
            if child.pid not in _disabled_ecoqos_pids:
                try:
                    h_proc = ctypes.windll.kernel32.OpenProcess(PROCESS_SET_INFORMATION, False, child.pid)
                    if h_proc:
                        try:
                            if disable_ecoqos_for_handle(h_proc):
                                _disabled_ecoqos_pids.add(child.pid)
                        except Exception:
                            pass
                        finally:
                            ctypes.windll.kernel32.CloseHandle(h_proc)
                except Exception:
                    pass
                    
        # Intersect with active PIDs to prune dead processes and handle PID recycling
        _disabled_ecoqos_pids &= active_pids
    except Exception:
        pass


def trigger_lockout_overlay(duration_seconds=20):
    """Enforce a fullscreen borderless Tkinter window to lockout visual focus with a Brain Dump phase."""
    # Check for High Stress Alert based on last 2 user reflections
    high_stress_alert = False
    try:
        reflections = db.get_reflections()
        latest_user_reflections = []
        for r in reversed(reflections):
            is_auto = r.get("summary", "").startswith("[Autopilot]")
            if not is_auto:
                latest_user_reflections.append(r)
                if len(latest_user_reflections) == 2:
                    break
        if len(latest_user_reflections) == 2:
            stress_flags = []
            for ur in latest_user_reflections:
                e = ur.get("energy_level", 5)
                f = ur.get("friction_level", 1)
                if e <= 2 or f >= 4:
                    stress_flags.append(True)
                else:
                    stress_flags.append(False)
            if all(stress_flags):
                high_stress_alert = True
    except Exception as e:
        print(f"Error checking stress in lockout: {e}")

    if high_stress_alert:
        duration_seconds = max(120, duration_seconds * 2)

    # Play a peaceful, soft, rising wind chime arpeggio (C4, E4, G4, B4, C5)
    play_beep_sequence([
        (262, 120),  # C4
        (330, 120),  # E4
        (392, 120),  # G4
        (494, 120),  # B4
        (523, 200)   # C5
    ])

    # Dynamic Theme Configuration
    root_bg = "#0b132b" if high_stress_alert else "#0b0f19"
    frame_bg = "#1c2541" if high_stress_alert else "#0e0e1a"
    highlight_color = "#3a506b" if high_stress_alert else "#2e2e4f"
    text_color = "#eaeaf2"
    desc_color = "#9d9db8"
    accent_purple = "#b49aff"
    accent_green = "#38bdf8" if high_stress_alert else "#2dd4a8"

    root = tk.Tk()
    root.title("MIND-FLOW // Cognitive Shield Lockout")
    root.overrideredirect(True)
    root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
    root.attributes("-topmost", True)
    root.configure(bg=root_bg)

    active_goal = db.get_current_goal()
    captured_dump = ""
    phase1_active = True
    grace_remaining = 15
    completed_fully = False
    snoozed = False
    breathing_mode = "box"

    frame = tk.Frame(
        root, bg=frame_bg, bd=1, relief="solid", 
        highlightbackground=highlight_color, highlightthickness=1, padx=45, pady=40
    )
    frame.place(relx=0.5, rely=0.5, anchor="center")

    title_text = "🌸 DEEP RECOVERY INTERVENTION 🌸" if high_stress_alert else "🌿 COGNITIVE SAVE-STATE 🌿"
    title_label = tk.Label(
        frame, text=title_text,
        font=("Outfit", 22, "bold"), fg=accent_purple if not high_stress_alert else accent_green, bg=frame_bg
    )
    title_label.pack(pady=(5, 10))

    if active_goal:
        goal_label = tk.Label(
            frame, text=f"🎯 FOCUS INTENTION: {active_goal}",
            font=("Inter", 12, "bold"), fg=accent_purple, bg=frame_bg, wraplength=600
        )
        goal_label.pack(pady=(0, 10))

    desc_text = "MIND-FLOW has detected high persistent stress. A deep recovery break is active to restore focus." if high_stress_alert else "Write down your active thoughts or next steps to safely pause your flow."
    desc_label = tk.Label(
        frame, text=desc_text,
        font=("Inter", 12), fg=desc_color, bg=frame_bg
    )
    desc_label.pack(pady=5)

    text_box = tk.Text(
        frame, width=55, height=4, font=("Inter", 13),
        bg="#0b132b" if high_stress_alert else "#0f0f1b", fg=text_color, insertbackground=accent_purple,
        bd=0, highlightbackground=highlight_color, highlightcolor=accent_purple,
        highlightthickness=1, padx=15, pady=15
    )
    text_box.pack(pady=15)
    text_box.focus_set()

    timer_label = tk.Label(
        frame, text=f"Grace period: {grace_remaining} seconds remaining",
        font=("Outfit", 12, "bold"), fg=accent_purple, bg=frame_bg
    )
    timer_label.pack(pady=5)

    btn_frame = tk.Frame(frame, bg=frame_bg)
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

    def submit_snooze():
        nonlocal snoozed
        snoozed = True
        root.destroy()

    save_btn = tk.Button(
        btn_frame, text="Save & Rest (Ctrl+Enter)", font=("Inter", 11, "bold"),
        bg="#8b5cf6", fg="#ffffff", activebackground="#7c3aed", activeforeground="#ffffff",
        bd=0, padx=20, pady=10, cursor="hand2", command=submit_dump
    )
    save_btn.pack(side="left", padx=10)

    snooze_btn = tk.Button(
        btn_frame, text="Snooze (2 Min) (Ctrl+S)", font=("Inter", 11, "bold"),
        bg="#374151", fg="#eaeaf2", activebackground="#4b5563", activeforeground="#ffffff",
        bd=0, padx=20, pady=10, cursor="hand2", command=submit_snooze
    )
    snooze_btn.pack(side="left", padx=10)

    def on_btn_enter(e):
        save_btn.config(bg="#7c3aed")
    def on_btn_leave(e):
        save_btn.config(bg="#8b5cf6")
    save_btn.bind("<Enter>", on_btn_enter)
    save_btn.bind("<Leave>", on_btn_leave)

    def on_snooze_enter(e):
        snooze_btn.config(bg="#4b5563")
    def on_snooze_leave(e):
        snooze_btn.config(bg="#374151")
    snooze_btn.bind("<Enter>", on_snooze_enter)
    snooze_btn.bind("<Leave>", on_snooze_leave)

    root.bind("<Control-Return>", submit_dump)
    root.bind("<Control-s>", lambda event: submit_snooze())
    root.bind("<Control-S>", lambda event: submit_snooze())

    def emergency_exit(event):
        root.destroy()
    root.bind("<Escape>", emergency_exit)

    def start_lockout_phase():
        text_box.pack_forget()
        timer_label.pack_forget()
        btn_frame.pack_forget()
        desc_label.pack_forget()

        title_label.config(text="🌸 MINDFUL RECHARGE TIME 🌸", fg=accent_green)
        
        anchor_title = tk.Label(
            frame, text="YOUR SECURED FLOW STATE:",
            font=("Outfit", 11, "bold"), fg="#fbbf24", bg=frame_bg
        )
        anchor_title.pack(pady=(15, 2))

        display_text = f'"{captured_dump}"' if captured_dump else "[No thought saved - brain clean]"
        anchor_msg = tk.Label(
            frame, text=display_text, font=("Inter", 15, "italic", "bold"),
            fg=accent_green, bg=frame_bg, wraplength=600, justify="center"
        )
        anchor_msg.pack(pady=12)

        rule_label = tk.Label(
            frame, text="THE 20-20-20 RULE:\nLook away from your screen at an object 20 feet away\nfor 20 seconds to reset eye strain and cognitive focus.",
            font=("Inter", 12, "italic"), fg=desc_color, bg=frame_bg, justify="center"
        )
        rule_label.pack(pady=12)

        STRESS_SELF_CARE = [
            "Drop your shoulders, unclamp your jaw, and let your hands rest flat on your lap.",
            "Close your eyes. Listen to the room around you. Sense the gravity holding you in your seat.",
            "Take a very slow sip of water. Feel the cool temperature as it refreshes you.",
            "Gently roll your neck in a slow circle. Let go of the urge to compile or solve.",
            "Look out the window at the sky. Focus on a cloud or distant tree. Let your vision widen."
        ]

        if high_stress_alert:
            selected_tip = random.choice(STRESS_SELF_CARE)
            stretch_label = tk.Label(
                frame, text=f"💪 DEEP SELF-CARE TIP:\n{selected_tip}",
                font=("Inter", 11, "bold"), fg="#fbbf24", bg=frame_bg, justify="center", wraplength=600
            )
        else:
            selected_stretch = random.choice(PHYSICAL_STRETCHES)
            stretch_label = tk.Label(
                frame, text=f"💪 PHYSICAL RECHARGE TIP:\n{selected_stretch}",
                font=("Inter", 11, "bold"), fg="#fbbf24", bg=frame_bg, justify="center", wraplength=600
            )
        stretch_label.pack(pady=6)

        selected_eye = random.choice(EYE_EXERCISES)
        eye_label = tk.Label(
            frame, text=f"👀 EYE RECOVERY TIP:\n{selected_eye}",
            font=("Inter", 11, "bold"), fg="#38bdf8", bg=frame_bg, justify="center", wraplength=600
        )
        eye_label.pack(pady=6)

        nonlocal lockout_timer_label
        lockout_timer_label = tk.Label(
            frame, text=f"{duration_seconds} seconds remaining",
            font=("Outfit", 18, "bold"), fg=text_color, bg=frame_bg
        )
        lockout_timer_label.pack(pady=10)

        # Toggle breathing rhythm controls
        toggle_breathing_frame = tk.Frame(frame, bg=frame_bg)
        toggle_breathing_frame.pack(pady=(5, 5))

        # Breathing guide label packed directly under toggle frame
        breathing_desc_label = tk.Label(
            frame, text="Box Breathing (4-4-4-4): Inhale 4s -> Hold 4s -> Exhale 4s -> Hold 4s.\nBest for regulating the nervous system and resetting mental fatigue.",
            font=("Inter", 10, "italic"), fg=desc_color, bg=frame_bg,
            wraplength=600, justify="center"
        )
        breathing_desc_label.pack(pady=(5, 10))

        def set_breathing_mode(mode):
            nonlocal breathing_mode, start_anim_time
            breathing_mode = mode
            start_anim_time = time.time()
            
            # Reset all button backgrounds
            box_btn.config(bg="#374151", fg="#eaeaf2")
            anxiety_btn.config(bg="#374151", fg="#eaeaf2")
            coherent_btn.config(bg="#374151", fg="#eaeaf2")
            
            if mode == "box":
                box_btn.config(bg="#8b5cf6", fg="#ffffff")
                breathing_desc_label.config(
                    text="Box Breathing (4-4-4-4): Inhale 4s -> Hold 4s -> Exhale 4s -> Hold 4s.\nBest for regulating the nervous system and resetting mental fatigue."
                )
            elif mode == "coherent":
                coherent_btn.config(bg="#fbbf24", fg="#0b0f19")
                breathing_desc_label.config(
                    text="Coherent Breathing (5-5): Inhale 5s -> Exhale 5s.\nBest for stabilizing heart rate variability and inducing calm alert focus."
                )
            else:
                anxiety_btn.config(bg=accent_green, fg="#0b0f19")
                breathing_desc_label.config(
                    text="Anxiety Relief (4-7-8): Inhale 4s -> Hold 7s -> Exhale 8s.\nBest for reducing stress, slowing heart rate, and calming nervous energy."
                )

        box_btn = tk.Button(
            toggle_breathing_frame, text="Box (4-4-4-4)", font=("Inter", 9, "bold"),
            bg="#8b5cf6", fg="#ffffff", activebackground="#7c3aed", activeforeground="#ffffff",
            bd=0, padx=10, pady=5, cursor="hand2", command=lambda: set_breathing_mode("box")
        )
        box_btn.pack(side="left", padx=5)

        coherent_btn = tk.Button(
            toggle_breathing_frame, text="Coherent (5-5)", font=("Inter", 9, "bold"),
            bg="#374151", fg="#eaeaf2", activebackground="#fbbf24", activeforeground="#0b0f19",
            bd=0, padx=10, pady=5, cursor="hand2", command=lambda: set_breathing_mode("coherent")
        )
        coherent_btn.pack(side="left", padx=5)

        anxiety_btn = tk.Button(
            toggle_breathing_frame, text="4-7-8 Anxiety Relief", font=("Inter", 9, "bold"),
            bg="#374151", fg="#eaeaf2", activebackground=accent_green, activeforeground="#0b0f19",
            bd=0, padx=10, pady=5, cursor="hand2", command=lambda: set_breathing_mode("anxiety")
        )
        anxiety_btn.pack(side="left", padx=5)

        nonlocal canvas
        canvas = tk.Canvas(frame, width=500, height=180, bg=frame_bg, bd=0, highlightthickness=0)
        canvas.pack(pady=10)
        canvas.create_line(50, 90, 450, 90, fill="#23233b" if not high_stress_alert else "#3a506b", dash=(2, 4))
        
        bubble_id = canvas.create_oval(0, 0, 0, 0, fill=accent_green, outline="#5eead4", width=2)
        instruction_text_id = canvas.create_text(0, 0, text="", font=("Inter", 9, "bold"), fill="#ffffff")
        
        # Rounded progress bar track and indicator at the bottom of the canvas
        canvas.create_line(50, 165, 450, 165, fill="#1e293b" if not high_stress_alert else "#2e3a4e", width=4, capstyle="round")
        progress_bar_id = canvas.create_line(50, 165, 50, 165, fill=accent_purple, width=4, capstyle="round")

        start_anim_time = time.time()
        
        def animate_relaxation():
            if not phase1_active and lockout_remaining > 0:
                try:
                    elapsed = time.time() - start_anim_time
                    cy = 90
                    
                    if breathing_mode == "box":
                        # Box breathing: 4s inhale, 4s hold, 4s exhale, 4s hold (16s cycle)
                        angle = (elapsed * 2 * math.pi) / 8.0
                        cx_pos = 250 + 160 * math.cos(angle)
                        breath_cycle = elapsed % 16.0
                        if breath_cycle < 4.0:
                            fraction = breath_cycle / 4.0
                            radius = 25 + 30 * fraction
                            text = "INHALE..."
                            color = "#2dd4a8"
                            outline_color = "#5eead4"
                        elif breath_cycle < 8.0:
                            radius = 55
                            text = "HOLD..."
                            color = "#fbbf24"
                            outline_color = "#fcd34d"
                        elif breath_cycle < 12.0:
                            fraction = (breath_cycle - 8.0) / 4.0
                            radius = 55 - 30 * fraction
                            text = "EXHALE..."
                            color = "#b49aff"
                            outline_color = "#c084fc"
                        else:
                            radius = 25
                            text = "HOLD..."
                            color = "#f43f5e"
                            outline_color = "#fda4af"
                    elif breathing_mode == "coherent":
                        # Coherent breathing: 5s inhale, 5s exhale (10s cycle)
                        angle = (elapsed * 2 * math.pi) / 5.0
                        cx_pos = 250 + 160 * math.cos(angle)
                        breath_cycle = elapsed % 10.0
                        if breath_cycle < 5.0:
                            fraction = breath_cycle / 5.0
                            radius = 25 + 30 * fraction
                            text = "INHALE..."
                            color = "#fbbf24"
                            outline_color = "#fcd34d"
                        else:
                            fraction = (breath_cycle - 5.0) / 5.0
                            radius = 55 - 30 * fraction
                            text = "EXHALE..."
                            color = "#3b82f6"
                            outline_color = "#60a5fa"
                    else:
                        # 4-7-8 breathing: Inhale 4s, Hold 7s, Exhale 8s (19s cycle)
                        angle = (elapsed * 2 * math.pi) / 9.5
                        cx_pos = 250 + 160 * math.cos(angle)
                        breath_cycle = elapsed % 19.0
                        if breath_cycle < 4.0:
                            fraction = breath_cycle / 4.0
                            radius = 25 + 30 * fraction
                            text = "INHALE (4S)..."
                            color = "#2dd4a8"
                            outline_color = "#5eead4"
                        elif breath_cycle < 11.0:
                            radius = 55
                            text = "HOLD (7S)..."
                            color = "#fbbf24"
                            outline_color = "#fcd34d"
                        else:
                            fraction = (breath_cycle - 11.0) / 8.0
                            radius = 55 - 30 * fraction
                            text = "EXHALE (8S)..."
                            color = "#3b82f6"
                            outline_color = "#60a5fa"
                    
                    canvas.itemconfig(bubble_id, fill=color, outline=outline_color)
                    canvas.itemconfig(instruction_text_id, text=text)
                    canvas.coords(bubble_id, cx_pos - radius, cy - radius, cx_pos + radius, cy + radius)
                    canvas.coords(instruction_text_id, cx_pos, cy)
                    
                    # Update active progress bar width
                    progress_pct = 1.0 - (lockout_remaining / duration_seconds) if duration_seconds > 0 else 0
                    progress_pct = max(0.0, min(1.0, progress_pct))
                    canvas.coords(progress_bar_id, 50, 165, 50 + 400 * progress_pct, 165)
                    
                    canvas.after(40, animate_relaxation)
                except Exception:
                    pass
        
        animate_relaxation()

        esc_label = tk.Label(
            frame, text="Press ESCAPE to bypass in case of emergency.",
            font=("Inter", 9), fg="#5c5c78", bg=frame_bg
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
            root.after(1000, update_lockout_countdown)
        else:
            nonlocal completed_fully
            completed_fully = True
            play_beep_sequence([
                (392, 120),  # G4
                (523, 120),  # C5
                (659, 250)   # E5
            ])
            root.destroy()
 
    update_grace_countdown()
    root.mainloop()
    return captured_dump, completed_fully, snoozed

# Import state dictionary from server backend to synchronize API mutations
from backend.server import shared_state, db, run_server

def main_state_machine(gui_process=None):
    """Background thread checking active windows and tracking idle state."""
    print("MIND-FLOW Core State Machine started.")

    # Seed initial daily reflection if none exist for today (optimized with reverse search)
    try:
        from datetime import date
        today_str = date.today().isoformat()
        reflections = db.get_reflections()
        has_today_refl = False
        for r in reversed(reflections):
            if r["timestamp"].startswith(today_str):
                has_today_refl = True
                break
            try:
                if datetime.fromisoformat(r["timestamp"]).date() < date.today():
                    break
            except:
                pass
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
    
    # Caches to prevent scanning database collections every second
    reflections_cache = {
        "len": -1,
        "latest_today": None,
        "last_checked_date": None
    }
    sessions_cache = {
        "len": -1,
        "bypasses_today": 0,
        "last_checked_date": None
    }

    # Set up loop counter and run initial EcoQoS disabling
    loop_counter = 0
    disable_ecoqos_for_process_tree()

    while True:
        time.sleep(1.0)
        loop_counter += 1
        if loop_counter % 60 == 0:
            disable_ecoqos_for_process_tree()
        
        # Check if standalone GUI process exited
        if gui_process and hasattr(gui_process, 'poll') and gui_process.poll() is not None:
            print("MIND-FLOW dashboard window closed.")
            
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


        # Determine target mode
        target_mode = "neutral"
        if idle_sec_val >= idle_limit:
            target_mode = "rest"
        else:
            is_work = any(matches_keyword(kw, process_lower, pre_lowercased=True) or matches_keyword(kw, title_lower, pre_lowercased=True) for kw in work_keywords)
            is_recharge = any(matches_keyword(kw, process_lower, pre_lowercased=True) or matches_keyword(kw, title_lower, pre_lowercased=True) for kw in recharge_keywords)

            if is_work:
                target_mode = "work"
            elif is_recharge:
                target_mode = "recharge"

        # Check if Mode transition occurred
        if target_mode != current_mode:
            now = datetime.now()
            print(f"State transition: {current_mode} -> {target_mode}")
            
            if target_mode == "rest" and current_mode in ["work", "recharge", "neutral"]:
                from datetime import timedelta
                transition_time = max(state_start_time, now - timedelta(seconds=idle_limit))
                db.log_session(current_mode, state_start_time, transition_time)
                state_start_time = transition_time
            else:
                db.log_session(current_mode, state_start_time, now)
                state_start_time = now
                
            current_mode = target_mode
            shared_state["current_mode"] = current_mode
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
                
                from datetime import timedelta
                brain_dump, completed, snoozed = trigger_lockout_overlay(rest_limit_sec)
                if snoozed:
                    print("Hard focus ceiling snoozed. Giving 2 minutes grace period.")
                    state_start_time = datetime.now() - timedelta(seconds=max(0, work_limit_sec - 120))
                    shared_state["elapsed_seconds"] = int((datetime.now() - state_start_time).total_seconds())
                else:
                    db.log_session("work", state_start_time, datetime.now(), brain_dump=brain_dump, bypassed=not completed)
                    state_start_time = datetime.now()
                    shared_state["elapsed_seconds"] = 0

        # Automated energy battery tracking (Auto-decay/recharge check)
        try:
            today_date = date.today()
            today_str = today_date.isoformat()
            reflections = db.get_reflections()
            
            # Fetch latest reflection (only scan if length of reflections list changed or date changed)
            if len(reflections) != reflections_cache["len"] or reflections_cache["last_checked_date"] != today_date:
                latest_refl = None
                for r in reversed(reflections):
                    if r["timestamp"].startswith(today_str):
                        latest_refl = r
                        break
                    try:
                        if datetime.fromisoformat(r["timestamp"]).date() < today_date:
                            break
                    except:
                        pass
                reflections_cache["len"] = len(reflections)
                reflections_cache["latest_today"] = latest_refl
                reflections_cache["last_checked_date"] = today_date
            else:
                latest_refl = reflections_cache["latest_today"]
            
            if latest_refl:
                current_energy = latest_refl.get("energy_level", 5)
                last_refl_time = datetime.fromisoformat(latest_refl["timestamp"])
                elapsed_since_refl = (datetime.now() - last_refl_time).total_seconds()
                
                if current_mode == "work":
                    if elapsed_since_refl >= 300:
                        if current_energy > 1:
                            new_energy = current_energy - 1
                            
                            # Fetch bypasses (only scan if length of sessions list changed or date changed)
                            sessions = db.get_sessions()
                            if len(sessions) != sessions_cache["len"] or sessions_cache["last_checked_date"] != today_date:
                                bypasses_today = 0
                                for s in reversed(sessions):
                                    if s["start"].startswith(today_str):
                                        if s.get("bypassed", False):
                                            bypasses_today += 1
                                    else:
                                        try:
                                            if datetime.fromisoformat(s["start"]).date() < today_date:
                                                break
                                        except:
                                            pass
                                sessions_cache["len"] = len(sessions)
                                sessions_cache["bypasses_today"] = bypasses_today
                                sessions_cache["last_checked_date"] = today_date
                            else:
                                bypasses_today = sessions_cache["bypasses_today"]
                            
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

def run_webview_gui(url):
    """Run a standalone pywebview Edge WebView2 window."""
    import webview
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
    
    # 2. Start periodic background EcoQoS disabling for child processes
    def periodic_disable_throttling():
        while True:
            time.sleep(60.0)
            disable_ecoqos_for_process_tree()
            
    throttling_thread = threading.Thread(target=periodic_disable_throttling, daemon=True)
    throttling_thread.start()
    
    # 3. WebView window setup
    # Set background color to #0b0f19 to avoid white flash
    window = webview.create_window(
        "MIND-FLOW // Cognitive Companion Dashboard",
        url,
        width=1280,
        height=800,
        background_color="#0b0f19"
    )
    webview.start(debug=False)

# Original pywebview standalone app launcher restored
def launch_app_window(url):
    """Launch the dashboard url in a standalone pywebview GUI subprocess."""
    import sys
    import subprocess
    import os
    
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
    # Clean up Windows registry overrides to let the OS route GPU preferences naturally
    try:
        if sys.platform == "win32":
            import winreg
            key_path = r"Software\Microsoft\DirectX\UserGpuPreferences"
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
                try:
                    winreg.DeleteValue(key, sys.executable)
                except FileNotFoundError:
                    pass
                if hasattr(sys, "_base_executable") and sys._base_executable != sys.executable:
                    try:
                        winreg.DeleteValue(key, sys._base_executable)
                    except FileNotFoundError:
                        pass
                
                # Delete any registered webview runtimes
                try:
                    idx = 0
                    to_delete = []
                    while True:
                        try:
                            name, val, type_ = winreg.EnumValue(key, idx)
                            if name.lower().endswith("msedgewebview2.exe"):
                                to_delete.append(name)
                            idx += 1
                        except OSError:
                            break
                    for name in to_delete:
                        try:
                            winreg.DeleteValue(key, name)
                        except FileNotFoundError:
                            pass
                except Exception:
                    pass
                
                winreg.CloseKey(key)
            except FileNotFoundError:
                pass
    except Exception:
        pass

    # Use standard priority scheduling class to prevent background console OS-throttling overrides
    pass

    # Disable EcoQoS/Power Throttling for current process initially
    try:
        disable_ecoqos_for_process_tree()
    except Exception:
        pass

    # If --gui argument is passed, launch the pywebview standalone window process
    if len(sys.argv) > 1 and sys.argv[1] == "--gui":
        run_webview_gui("http://127.0.0.1:5000")
        sys.exit(0)

    # 1. Start Server in a separate daemon thread
    server_thread = threading.Thread(target=run_server, kwargs={"port": 5000}, daemon=True)
    server_thread.start()
    
    # Wait a brief moment for Flask to initialize
    time.sleep(0.5)

    # 2. Open dashboard in native app window (pywebview process)
    print("Launching Cognitive Dashboard in Standalone App Mode...")
    gui_proc = launch_app_window("http://127.0.0.1:5000")

    # 3. Start state machine in the main thread (blocks execution)
    try:
        main_state_machine(gui_process=gui_proc)
    except KeyboardInterrupt:
        print("\nMIND-FLOW terminated by user.")
        sys.exit(0)
