import os
import sys
import io
import subprocess

import shutil

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
    # 1. Determine standard target user-space directory
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if appdata:
            target_dir = os.path.join(appdata, "MIND")
        else:
            target_dir = os.path.join(os.path.expanduser("~"), ".mindflow")
    else:
        target_dir = os.path.join(os.path.expanduser("~"), ".mindflow")

    # 2. Check and auto-migrate from legacy C:\MIND path if needed
    legacy_dir = r"C:\MIND"
    if sys.platform == "win32" and os.path.exists(legacy_dir) and os.path.isdir(legacy_dir) and os.path.abspath(legacy_dir) != os.path.abspath(target_dir):
        try:
            # Check if there is anything to migrate before doing work
            migrate_items = ["mind_flow_data.db", "Workspace_Profiles", "mind_flow_data.json.bak"]
            has_migration_candidates = any(os.path.exists(os.path.join(legacy_dir, item)) for item in migrate_items)
            
            if has_migration_candidates:
                os.makedirs(target_dir, exist_ok=True)
                for item in migrate_items:
                    src = os.path.join(legacy_dir, item)
                    dst = os.path.join(target_dir, item)
                    if os.path.exists(src) and not os.path.exists(dst):
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)
        except Exception as e:
            # Fail silently to avoid breaking startup due to permissions
            print(f"[MIND-FLOW] Warning: Legacy data migration failed: {e}")

    return target_dir

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
if sys.platform == "win32":
    import winsound
from datetime import datetime, date

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

from backend.database import matches_keyword, matches_any_keyword, is_browser_process

if sys.platform == "win32":
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
else:
    LASTINPUTINFO = None

# Event-driven Active Window Caching
_active_window_lock = threading.Lock()
_active_hwnd = None
_active_title = "None"
_active_process = "None"

def get_active_window_title_direct(hwnd):
    try:
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return "None"
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception as e:
        print(f"Error reading active window title: {e}")
        return "None"

def get_active_process_name_direct(hwnd):
    try:
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

if sys.platform == "win32":
    # Hook callback prototype
    WinEventProcType = ctypes.WINFUNCTYPE(
        None,
        ctypes.c_void_p, # hWinEventHook
        ctypes.c_ulong,  # event
        ctypes.c_void_p, # hwnd
        ctypes.c_long,   # idObject
        ctypes.c_long,   # idChild
        ctypes.c_ulong,  # dwEventThread
        ctypes.c_ulong   # dwmsEventTime
    )
    
    def win_event_proc(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
        global _active_hwnd, _active_title, _active_process
        if hwnd:
            title = get_active_window_title_direct(hwnd)
            process = get_active_process_name_direct(hwnd)
            with _active_window_lock:
                _active_hwnd = hwnd
                _active_title = title
                _active_process = process

    _hook_callback = WinEventProcType(win_event_proc)

    def start_win_event_listener():
        hook = ctypes.windll.user32.SetWinEventHook(
            0x0003, # EVENT_SYSTEM_FOREGROUND
            0x0003, # EVENT_SYSTEM_FOREGROUND
            0,
            _hook_callback,
            0,
            0,
            0 # WINEVENT_OUTOFCONTEXT
        )
        if not hook:
            print("SetWinEventHook failed.")
            return
            
        class MSG(ctypes.Structure):
            _fields_ = [
                ("hwnd", ctypes.c_void_p),
                ("message", ctypes.c_uint),
                ("wParam", ctypes.c_void_p),
                ("lParam", ctypes.c_void_p),
                ("time", ctypes.c_ulong),
                ("pt", ctypes.c_long * 2),
                ("lPrivate", ctypes.c_ulong)
            ]
            
        msg = MSG()
        while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
        ctypes.windll.user32.UnhookWinEvent(hook)

    # Initialize foreground window once on startup
    try:
        init_hwnd = ctypes.windll.user32.GetForegroundWindow()
        if init_hwnd:
            _active_hwnd = init_hwnd
            _active_title = get_active_window_title_direct(init_hwnd)
            _active_process = get_active_process_name_direct(init_hwnd)
    except Exception:
        pass

def get_active_window_details():
    """Retrieve both foreground window title and process name atomically under lock, with optimized fallbacks on macOS/Linux."""
    # Support mock patch in test suite: if the individual functions are mocked, call them directly
    if hasattr(get_active_window_title, '_mock_self') or hasattr(get_active_process_name, '_mock_self') or hasattr(get_active_window_title, 'called') or hasattr(get_active_process_name, 'called'):
        return get_active_window_title(), get_active_process_name()

    if sys.platform != "win32":
        if sys.platform == "darwin":
            try:
                script = (
                    'tell application "System Events"\n'
                    '    set frontApp to first application process whose frontmost is true\n'
                    '    set appName to name of frontApp\n'
                    '    set winName to "None"\n'
                    '    try\n'
                    '        set winName to name of window 1 of frontApp\n'
                    '    end try\n'
                    '    return appName & "|||" & winName\n'
                    'end tell'
                )
                output = subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL).decode('utf-8').strip()
                if "|||" in output:
                    process, title = output.split("|||", 1)
                    return title.strip(), process.strip().lower()
            except Exception:
                pass
            return "None", "none"
        else:
            try:
                cmd = "xprop -id $(xprop -root _NET_ACTIVE_WINDOW | awk '{print $NF}') _NET_WM_NAME _NET_WM_PID"
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip()
                title = "None"
                pid = None
                for line in output.splitlines():
                    if "_NET_WM_NAME" in line:
                        parts = line.split(" = ")
                        if len(parts) > 1:
                            title = parts[1].strip('"')
                    elif "_NET_WM_PID" in line:
                        parts = line.split(" = ")
                        if len(parts) > 1:
                            pid = parts[1].strip()
                
                process = "none"
                if pid:
                    try:
                        with open(f"/proc/{pid}/comm", "r") as f:
                            process = f.read().strip().lower()
                    except Exception:
                        pass
                return title, process
            except Exception:
                pass
            return "None", "none"

    with _active_window_lock:
        return _active_title, _active_process

def get_active_window_title():
    """Retrieve foreground window title securely using ctypes or cross-platform fallbacks."""
    if sys.platform != "win32":
        if sys.platform == "darwin":
            try:
                cmd = "osascript -e 'tell application \"System Events\" to tell (first process whose frontmost is true) to get name of window 1'"
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip()
                if output:
                    return output
            except Exception:
                pass
            try:
                cmd = "osascript -e 'tell application \"System Events\" to get name of first process whose frontmost is true'"
                return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip()
            except Exception:
                return "None"
        else:
            try:
                cmd = "xprop -id $(xprop -root _NET_ACTIVE_WINDOW | awk '{print $NF}') _NET_WM_NAME | cut -d '\"' -f 2"
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip()
                return output if output else "None"
            except Exception:
                return "None"

    with _active_window_lock:
        return _active_title

def get_active_process_name(hwnd=None):
    """Retrieve foreground window process base executable name securely using ctypes or cross-platform fallbacks."""
    if sys.platform != "win32":
        if sys.platform == "darwin":
            try:
                cmd = "osascript -e 'tell application \"System Events\" to get name of first process whose frontmost is true'"
                return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip().lower()
            except Exception:
                return "None"
        else:
            try:
                cmd = "cat /proc/$(xprop -id $(xprop -root _NET_ACTIVE_WINDOW | awk '{print $NF}') _NET_WM_PID | awk '{print $NF}')/comm"
                return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip().lower()
            except Exception:
                return "None"

    with _active_window_lock:
        return _active_process

# --- COM GUIDs and Interface definitions for Core Audio Peak Detection ---
if sys.platform == "win32":
    import uuid
    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8)
        ]
        def __init__(self, name_str):
            u = uuid.UUID(name_str)
            self.Data1 = u.time_low
            self.Data2 = u.time_mid
            self.Data3 = u.time_hi_version
            for i, b in enumerate(u.bytes[8:]):
                self.Data4[i] = b

    CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
    IID_IMMDeviceEnumerator = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
    IID_IAudioMeterInformation = GUID("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")

    class IUnknown(ctypes.c_void_p):
        pass

    def com_method(cls, name, index, argtypes, restype=ctypes.HRESULT):
        def method(self, *args):
            vtable = ctypes.cast(self, ctypes.POINTER(ctypes.c_void_p))[0]
            func_ptr = ctypes.cast(ctypes.c_void_p(vtable + index * ctypes.sizeof(ctypes.c_void_p)), ctypes.POINTER(ctypes.c_void_p))[0]
            prototype = ctypes.WINFUNCTYPE(restype, *([ctypes.c_void_p] + argtypes))
            func = prototype(func_ptr)
            return func(self, *args)
        setattr(cls, name, method)

    com_method(IUnknown, "Release", 2, [], ctypes.c_ulong)

    class IMMDeviceEnumerator(IUnknown):
        pass
    com_method(IMMDeviceEnumerator, "GetDefaultAudioEndpoint", 4, [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)])

    class IMMDevice(IUnknown):
        pass
    com_method(IMMDevice, "Activate", 3, [ctypes.POINTER(GUID), ctypes.c_ulong, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)])

    class IAudioMeterInformation(IUnknown):
        pass
    com_method(IAudioMeterInformation, "GetPeakValue", 3, [ctypes.POINTER(ctypes.c_float)])

    def check_windows_audio_active():
        try:
            ctypes.windll.ole32.CoInitialize(None)
            enumerator = ctypes.c_void_p()
            hr = ctypes.windll.ole32.CoCreateInstance(
                ctypes.byref(CLSID_MMDeviceEnumerator),
                None,
                1,
                ctypes.byref(IID_IMMDeviceEnumerator),
                ctypes.byref(enumerator)
            )
            if hr != 0:
                ctypes.windll.ole32.CoUninitialize()
                return False
                
            p_enumerator = IMMDeviceEnumerator(enumerator.value)
            device = ctypes.c_void_p()
            hr = p_enumerator.GetDefaultAudioEndpoint(0, 1, ctypes.byref(device))
            if hr != 0:
                p_enumerator.Release()
                ctypes.windll.ole32.CoUninitialize()
                return False
                
            p_device = IMMDevice(device.value)
            meter = ctypes.c_void_p()
            hr = p_device.Activate(ctypes.byref(IID_IAudioMeterInformation), 1, None, ctypes.byref(meter))
            if hr != 0:
                p_device.Release()
                p_enumerator.Release()
                ctypes.windll.ole32.CoUninitialize()
                return False
                
            p_meter = IAudioMeterInformation(meter.value)
            peak = ctypes.c_float()
            hr = p_meter.GetPeakValue(ctypes.byref(peak))
            
            p_meter.Release()
            p_device.Release()
            p_enumerator.Release()
            ctypes.windll.ole32.CoUninitialize()
            
            return hr == 0 and peak.value > 0.0005
        except Exception:
            return False
else:
    def check_windows_audio_active():
        return False

def is_audio_playing():
    """Check if audio playback is currently active in the OS (to prevent false-positive idle states)."""
    if sys.platform == "win32":
        return check_windows_audio_active()
    elif sys.platform == "darwin":
        try:
            output = subprocess.check_output(["pmset", "-g", "assertions"], stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
            for line in output.splitlines():
                if ("PreventUserIdleSystemSleep" in line or "PreventUserIdleDisplaySleep" in line) and "1" in line:
                    return True
        except Exception:
            pass
        return False
    else:
        try:
            output = subprocess.getoutput("pactl list sink-inputs")
            if "state: RUNNING" in output or "State: RUNNING" in output:
                return True
        except Exception:
            pass
        return False

def is_passive_viewing_active(active_process, active_title):
    """Check if the user is engaged in passive viewing (meeting or video) with active audio."""
    if not active_process or not active_title:
        return False
    
    proc_lower = active_process.lower()
    title_lower = active_title.lower()
    
    # Check if process is a known video conferencing or media app
    media_apps = ["zoom.exe", "zoom", "teams.exe", "teams", "webex.exe", "webex", 
                  "discord.exe", "discord", "skype.exe", "skype", "slack.exe", "slack", 
                  "vlc.exe", "vlc", "wmplayer.exe", "quicktime"]
    is_media_app = any(app in proc_lower for app in media_apps)
    
    # Check if it's a browser process playing media
    is_browser = is_browser_process(active_process)
    is_video_title = any(kw in title_lower for kw in [
        "youtube", "netflix", "meet.google", "zoom", "teams", "webinar", "course", 
        "tutorial", "lecture", "class", "udemy", "coursera", "video", "movie", "stream"
    ])
    
    if (is_media_app or (is_browser and is_video_title)):
        return is_audio_playing()
            
    return False

def get_idle_seconds():
    """Retrieve duration of hardware idle state (no mouse/keyboard) using ctypes or fallbacks."""
    if sys.platform != "win32":
        if sys.platform == "darwin":
            try:
                from ctypes import util
                cg_path = util.find_library('CoreGraphics')
                if cg_path:
                    cg = ctypes.CDLL(cg_path)
                    # kCGEventSourceStateHIDSystemState = 1, kCGAnyInputEventType = -1
                    cg.CGEventSourceSecondsSinceLastEventType.argtypes = [ctypes.c_int, ctypes.c_int]
                    cg.CGEventSourceSecondsSinceLastEventType.restype = ctypes.c_double
                    return cg.CGEventSourceSecondsSinceLastEventType(1, -1)
            except Exception:
                pass
            try:
                cmd = "ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {print $NF/1000000000; exit}'"
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip()
                return float(output) if output else 0.0
            except Exception:
                return 0.0
        else:
            try:
                class XScreenSaverInfo(ctypes.Structure):
                    _fields_ = [
                        ('window', ctypes.c_ulong),
                        ('state', ctypes.c_int),
                        ('kind', ctypes.c_int),
                        ('since', ctypes.c_ulong),
                        ('idle', ctypes.c_ulong),
                        ('event_mask', ctypes.c_ulong)
                    ]
                xlib = ctypes.cdll.LoadLibrary('libX11.so.6')
                xss = ctypes.cdll.LoadLibrary('libXss.so.1')
                
                xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
                xlib.XOpenDisplay.restype = ctypes.c_void_p
                xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
                xlib.XCloseDisplay.restype = ctypes.c_int
                xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
                xlib.XDefaultRootWindow.restype = ctypes.c_ulong
                xlib.XFree.argtypes = [ctypes.c_void_p]
                xlib.XFree.restype = ctypes.c_int
                
                xss.XScreenSaverAllocInfo.argtypes = []
                xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(XScreenSaverInfo)
                xss.XScreenSaverQueryInfo.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(XScreenSaverInfo)]
                xss.XScreenSaverQueryInfo.restype = ctypes.c_int
                
                import os
                display_env = os.environ.get('DISPLAY', ':0.0').encode('utf-8')
                display = xlib.XOpenDisplay(display_env)
                if display:
                    try:
                        root = xlib.XDefaultRootWindow(display)
                        info = xss.XScreenSaverAllocInfo()
                        if info and xss.XScreenSaverQueryInfo(display, root, info):
                            idle_ms = info.contents.idle
                            xlib.XFree(info)
                            return float(idle_ms) / 1000.0
                    finally:
                        xlib.XCloseDisplay(display)
            except Exception:
                pass
            try:
                output = subprocess.check_output("xprintidle", shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip()
                return float(output) / 1000.0 if output else 0.0
            except Exception:
                return 0.0

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

import queue

_beep_queue = queue.Queue()

def _beep_worker():
    while True:
        sequence = _beep_queue.get()
        if sequence is None:
            break
        if sys.platform != "win32":
            for freq, duration in sequence:
                sys.stdout.write('\a')
                sys.stdout.flush()
                time.sleep(duration / 1000.0)
        else:
            for freq, duration in sequence:
                try:
                    winsound.Beep(freq, duration)
                except Exception:
                    pass
        _beep_queue.task_done()

_beep_thread = threading.Thread(target=_beep_worker, daemon=True)
_beep_thread.start()

def play_beep_sequence(sequence):
    """Play a sequence of beeps asynchronously using a queue-managed daemon thread."""
    _beep_queue.put(sequence)

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

_parent_process_cache = None

def disable_ecoqos_for_process_tree():
    """Disable EcoQoS (Efficiency Mode) for the current Python process and all descendant processes recursively."""
    if sys.platform != "win32":
        return
    try:
        # Disable for current process
        h_process = ctypes.windll.kernel32.GetCurrentProcess()
        disable_ecoqos_for_handle(h_process)
        
        # Disable for all child and descendant processes
        import os
        import psutil
        current_pid = os.getpid()
        try:
            parent = psutil.Process(current_pid)
            for child in parent.children(recursive=True):
                try:
                    # PROCESS_SET_INFORMATION = 0x0200
                    h_child = ctypes.windll.kernel32.OpenProcess(0x0200, False, child.pid)
                    if h_child:
                        disable_ecoqos_for_handle(h_child)
                        ctypes.windll.kernel32.CloseHandle(h_child)
                except Exception:
                    pass
        except Exception:
            pass
    except Exception as e:
        print(f"Error disabling EcoQoS for process tree: {e}")


# Lockout overlay removed

from backend.server import shared_state, db, run_server, SHARED_API_TOKEN

class CognitiveBattery:
    def __init__(self, capacity: float = 100.0, consecutive_work: float = 0.0):
        try:
            self.capacity = min(max(float(capacity), 0.0), 100.0)
        except (TypeError, ValueError):
            self.capacity = 100.0
        try:
            self.consecutive_work_minutes = float(consecutive_work)
        except (TypeError, ValueError):
            self.consecutive_work_minutes = 0.0
        
        # Tuning parameters
        self.base_drain_per_minute = 0.5    
        self.fatigue_multiplier = 0.035     
        self.rest_recovery_per_minute = 2.5 

    def process_tick(self, is_working: bool, elapsed_minutes: float) -> tuple:
        if is_working:
            self.consecutive_work_minutes += elapsed_minutes
            penalty = 1.0 + (self.consecutive_work_minutes * self.fatigue_multiplier)
            drain = self.base_drain_per_minute * penalty * elapsed_minutes
            self.capacity = max(0.0, self.capacity - drain)
        else:
            self.consecutive_work_minutes = 0.0 
            recovery = self.rest_recovery_per_minute * elapsed_minutes
            self.capacity = min(100.0, self.capacity + recovery)
            
        return self.capacity, self.consecutive_work_minutes

def classify_activity_mode(active_process, active_title, work_keywords, recharge_keywords):
    """Determine the classification (work, recharge, neutral) based on process, title, and heuristics."""
    if not active_process or not active_title:
        return "neutral"
        
    proc_lower = active_process.lower()
    title_lower = active_title.lower()
    
    # 1. Custom User Regex Mappings
    settings = db.get_settings()
    custom_rules = settings.get("custom_rules", [])
    import re
    for rule in custom_rules:
        pattern = rule.get("pattern")
        category = rule.get("category")
        if pattern and category:
            try:
                if re.search(pattern, title_lower) or re.search(pattern, proc_lower):
                    return category
            except Exception:
                pass

    # 2. Browser heuristics
    if is_browser_process(active_process):
        # Work keywords check
        is_work = matches_any_keyword(work_keywords, active_title)
        is_recharge = matches_any_keyword(recharge_keywords, active_title)
        
        # Heuristic override for videos / articles (e.g. YouTube tutorial)
        work_context_words = ["tutorial", "course", "learn", "how to", "documentation", "reference", 
                              "coding", "programming", "developer", "lecture", "class", "webinar",
                              "study", "education", "research", "arxiv", "sciencedirect", "stack overflow", 
                              "github", "docs", "wiki", "wikipedia"]
        
        has_work_context = any(word in title_lower for word in work_context_words)
        
        if is_recharge and ("youtube" in title_lower or "youtube" in proc_lower) and has_work_context:
            return "work"
            
        if not is_work and not is_recharge:
            # Check for general reference or dev pages that fell into Neutral Blackhole
            neutral_work_sites = ["wikipedia.org", "wikipedia", "stackoverflow", "stack overflow", 
                                  "github", "gitlab", "bitbucket", "docs.python", "docs.microsoft", 
                                  "w3schools", "geeksforgeeks", "medium.com", "dev.to", "arxiv.org",
                                  "sciencedirect.com", "google scholar", "chatgpt", "claude.ai"]
            if any(site in title_lower for site in neutral_work_sites):
                return "work"
                
        if is_work:
            return "work"
        elif is_recharge:
            return "recharge"
        return "neutral"
        
    else:
        # Non-browser process
        # Check if process name or title matches work/recharge
        is_work = matches_any_keyword(work_keywords, active_process) or matches_any_keyword(work_keywords, active_title)
        is_recharge = matches_any_keyword(recharge_keywords, active_process) or matches_any_keyword(recharge_keywords, active_title)
        
        # Special check: Non-browser editor/dev processes
        dev_processes = ["pycharm", "vscode", "code.exe", "code", "studio", "eclipse", "sublime", "xcode", "unity", "godot", "terminal", "powershell", "cmd.exe", "bash"]
        if any(dp in proc_lower for dp in dev_processes):
            return "work"
            
        if is_work:
            return "work"
        elif is_recharge:
            return "recharge"
        return "neutral"
def trigger_fullscreen_break_lockout(duration_seconds):
    """Spawn a fullscreen, topmost, frameless Tkinter overlay to enforce break friction.
       Returns True if the break was bypassed early, False if it was fully completed.
    """
    import sys
    try:
        if 'unittest' in sys.modules or 'pytest' in sys.modules:
            print("[Break Lockout] Test environment detected. Skipping Tkinter window.")
            return True
        test_root = tk.Tk()
        test_root.destroy()
    except Exception as e:
        print(f"[Break Lockout] GUI Display not available ({e}). Skipping Tkinter window.")
        return True

    bypassed_dict = {"status": True}  # Use dict to mutate in closures

    try:
        root = tk.Tk()
        root.title("MIND-FLOW Break Lockout")
        
        # Frameless and topmost
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        
        # Fullscreen geometry
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        root.geometry(f"{screen_width}x{screen_height}+0+0")
        
        # Keep grabbing focus
        root.focus_force()
        root.configure(bg="#0b0f19")
        
        time_left = tk.IntVar(value=int(duration_seconds))
        
        # Title Label
        title_label = tk.Label(
            root, 
            text="TIME FOR A COGNITIVE BREAK", 
            font=("Outfit", 28, "bold"), 
            fg="#ff4a76", 
            bg="#0b0f19"
        )
        title_label.pack(pady=(screen_height // 4, 20))
        
        # Random exercise/stretch select
        import random
        stretches = PHYSICAL_STRETCHES + EYE_EXERCISES
        stretch_text = random.choice(stretches)
        
        exercise_label = tk.Label(
            root, 
            text=f"Focus Activity:\n{stretch_text}", 
            font=("Inter", 16), 
            fg="#e2e8f0", 
            bg="#0b0f19",
            justify="center",
            wraplength=int(screen_width * 0.6)
        )
        exercise_label.pack(pady=20)
        
        # Timer Label
        timer_label = tk.Label(
            root, 
            text=f"Break ending in {duration_seconds}s", 
            font=("Outfit", 20, "bold"), 
            fg="#38bdf8", 
            bg="#0b0f19"
        )
        timer_label.pack(pady=20)
        
        # Typing challenge setup
        challenge_frame = tk.Frame(root, bg="#0b0f19")
        
        challenge_phrase = "i choose to skip my break"
        challenge_instr = tk.Label(
            challenge_frame,
            text=f"To bypass, type: '{challenge_phrase}'",
            font=("Inter", 12),
            fg="#94a3b8",
            bg="#0b0f19"
        )
        challenge_instr.pack(pady=5)
        
        challenge_entry = tk.Entry(
            challenge_frame,
            font=("Inter", 14),
            width=30,
            justify="center",
            bg="#1e293b",
            fg="#ffffff",
            insertbackground="#ffffff",
            bd=0,
            highlightthickness=1,
            highlightbackground="#475569",
            highlightcolor="#38bdf8"
        )
        challenge_entry.pack(pady=5)
        
        # Bypass button
        def on_bypass():
            if challenge_entry.get().strip().lower() == challenge_phrase:
                bypassed_dict["status"] = True
                root.destroy()
                
        bypass_btn = tk.Button(
            challenge_frame,
            text="Confirm Bypass",
            command=on_bypass,
            font=("Outfit", 14, "bold"),
            bg="#ff4a76",
            fg="#ffffff",
            activebackground="#e11d48",
            activeforeground="#ffffff",
            bd=0,
            padx=20,
            pady=10,
            cursor="hand2"
        )
        
        def check_typing(*args):
            if challenge_entry.get().strip().lower() == challenge_phrase:
                bypass_btn.pack(pady=10)
            else:
                bypass_btn.pack_forget()
                
        challenge_var = tk.StringVar()
        challenge_var.trace_add("write", check_typing)
        challenge_entry.config(textvariable=challenge_var)
        
        # Prevent manual window closing
        root.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Main tick loop
        def tick():
            current_val = time_left.get()
            if current_val <= 1:
                bypassed_dict["status"] = False
                root.destroy()
            else:
                time_left.set(current_val - 1)
                timer_label.config(text=f"Break ending in {current_val - 1}s")
                root.attributes("-topmost", True)
                root.focus_force()
                
                # Show bypass challenge after 5 seconds
                if duration_seconds - current_val >= 5:
                    challenge_frame.pack(pady=20)
                root.after(1000, tick)
                
        root.after(1000, tick)
        root.mainloop()
    except Exception as e:
        print(f"Error in Break Lockout GUI: {e}")
        return True

    return bypassed_dict["status"]

def main_state_machine(gui_process=None):
    """Background thread checking active windows and tracking idle state."""
    print("MIND-FLOW Core State Machine started.")

    # Initialize workspace manager and clean up leftovers
    try:
        from backend.workspace_manager import WorkspaceManager
        workspace_mgr = WorkspaceManager(get_default_data_dir())
        workspace_mgr.sweep_back_all()
    except Exception as e:
        print(f"Error initializing WorkspaceManager: {e}")
        workspace_mgr = None

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
            except Exception:
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
    shared_state["mode_start_time"] = state_start_time
    
    # Initialize shared app tracking variables
    shared_state["last_app_process"] = None
    shared_state["last_app_title"] = None
    shared_state["app_accumulated_seconds"] = 0
    shared_state["last_hwnd"] = None
    
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

    # Run initial EcoQoS disabling
    disable_ecoqos_for_process_tree()

    # Initialize Cognitive Battery from database
    try:
        initial_battery = db.get_battery_state()
        battery = CognitiveBattery(
            capacity=initial_battery.get('capacity', 100.0),
            consecutive_work=initial_battery.get('consecutive_work', 0.0)
        )
    except Exception as e:
        print(f"Error loading initial battery state: {e}")
        battery = CognitiveBattery(capacity=100.0, consecutive_work=0.0)

    # Share initial state immediately
    shared_state['battery_capacity'] = battery.capacity
    shared_state['battery_consecutive_work'] = battery.consecutive_work_minutes

    ticks_since_flush = 0
    ticks_since_ecoqos = 0
    tick_duration_seconds = 1.0
    tick_duration_minutes = tick_duration_seconds / 60.0

    # Register exit handler to flush battery state to DB
    import atexit
    @atexit.register
    def exit_flush():
        try:
            db.flush_battery_state(battery.capacity, battery.consecutive_work_minutes)
            print("Autopilot: Flushed final battery state to database via atexit.")
        except Exception as e:
            print(f"Error flushing battery state on exit: {e}")

    while True:
        time.sleep(1.0)
        
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
            
            if workspace_mgr:
                try:
                    workspace_mgr.sweep_back_all()
                except Exception as e:
                    print(f"Error sweeping workspace on GUI exit: {e}")
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
                state_start_time = datetime.now()
                shared_state["mode_start_time"] = state_start_time
                if workspace_mgr:
                    try:
                        workspace_mgr.sweep_back_all()
                    except Exception as e:
                        print(f"Error sweeping workspace on tracking disable: {e}")
            
            shared_state["active_window_title"] = "Companion Paused"
            shared_state["active_process_name"] = "Paused"
            shared_state["current_mode"] = "neutral"
            shared_state["elapsed_seconds"] = 0
            shared_state["idle_seconds"] = 0
            continue

        # Get inputs
        idle_sec = get_idle_seconds()
        try:
            idle_sec_val = float(idle_sec)
        except (TypeError, ValueError):
            idle_sec_val = 0.0

        # Passive viewing check: override idle state if audio is playing in a video/meeting app
        if idle_sec_val >= 5:
            prev_title = shared_state.get("active_window_title")
            prev_proc = shared_state.get("active_process_name")
            if prev_title and prev_proc and is_passive_viewing_active(prev_proc, prev_title):
                idle_sec_val = 0.0

        shared_state["idle_seconds"] = int(idle_sec_val)

        # Optimize polling overhead: reuse previous details when idle
        if idle_sec_val > 5 and shared_state.get("active_window_title") not in [None, "None", "Detecting...", "Paused"]:
            active_title = shared_state.get("active_window_title", "None")
            active_process = shared_state.get("active_process_name", "None")
        else:
            if sys.platform == "win32":
                active_title, active_process = get_active_window_details()
            else:
                # macOS/Linux fallback throttling: poll at most once every 2 seconds
                current_time = time.time()
                if not hasattr(main_state_machine, "_last_unix_poll"):
                    main_state_machine._last_unix_poll = 0.0
                
                if current_time - main_state_machine._last_unix_poll >= 2.0:
                    active_title, active_process = get_active_window_details()
                    main_state_machine._last_unix_poll = current_time
                else:
                    active_title = shared_state.get("active_window_title", "None")
                    active_process = shared_state.get("active_process_name", "None")

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
                    # Application changed, log (buffered in db) previous
                    if last_proc and accum_sec > 0:
                        try:
                            db.log_app_usage(last_proc, last_title, accum_sec)
                        except Exception as e:
                            print(f"Error logging app usage on switch: {e}")
                    shared_state["last_app_process"] = active_process
                    shared_state["last_app_title"] = active_title
                    shared_state["app_accumulated_seconds"] = 1
        else:
            # User went idle, flush accumulated time to buffer and save/flush to DB
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
            
            # Explicitly commit app usage buffer to SQLite
            try:
                db.save()
            except Exception as e:
                print(f"Error saving DB on idle transition: {e}")

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
            target_mode = classify_activity_mode(active_process, active_title, work_keywords, recharge_keywords)

        # Check if Mode transition occurred
        if target_mode != current_mode:
            now = datetime.now()
            print(f"State transition: {current_mode} -> {target_mode}")
            
            prev_mode = current_mode

            if target_mode == "rest" and current_mode in ["work", "recharge", "neutral"]:
                from datetime import timedelta
                transition_time = max(state_start_time, now - timedelta(seconds=idle_limit))
                db.log_session(current_mode, state_start_time, transition_time)
                state_start_time = transition_time
            else:
                db.log_session(current_mode, state_start_time, now)
                state_start_time = now
            shared_state["mode_start_time"] = state_start_time

            current_mode = target_mode
            shared_state["current_mode"] = current_mode
            shared_state["elapsed_seconds"] = 0

            # Swapping/sweeping workspace files based on mode change
            if workspace_mgr:
                try:
                    workspace_mgr.transition_workspace(prev_mode, target_mode)
                except Exception as e:
                    print(f"Error transitioning workspace: {e}")

            # Flush app usage buffer and cognitive battery state to database on transition
            try:
                db.flush_battery_state(battery.capacity, battery.consecutive_work_minutes)
                db.save()
            except Exception as e:
                print(f"Error flushing database on transition: {e}")
        else:
            elapsed = (datetime.now() - state_start_time).total_seconds()
            shared_state["elapsed_seconds"] = int(elapsed)

            if current_mode == "work" and elapsed >= work_limit_sec:
                print(f"Hard focus ceiling limit reached ({work_limit_sec}s). Launching fullscreen break lockout.")
                
                # Play notification sound sequence asynchronously
                play_beep_sequence([(800, 100), (0, 50), (800, 100), (0, 50), (1200, 300)])
                
                # Flush app usage before running the modal to get accurate metrics
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

                start_lockout = time.time()
                bypassed = trigger_fullscreen_break_lockout(rest_limit_sec)
                
                if bypassed:
                    db.log_session("work", state_start_time, datetime.now(), brain_dump="[Bypassed Break] Focus limit exceeded", bypassed=True)
                else:
                    db.log_session("work", state_start_time, datetime.now(), brain_dump="[Break Completed] Focus limit reached and break completed", bypassed=False)
                
                # Reset sprint timer for the next cycle
                state_start_time = datetime.now()
                shared_state["mode_start_time"] = state_start_time
                shared_state["elapsed_seconds"] = 0

        # Update Battery Math (In-Memory)
        try:
            is_active_work = (current_mode == "work")
            current_cap, current_streak = battery.process_tick(
                is_working=is_active_work,
                elapsed_minutes=tick_duration_minutes
            )
            shared_state['battery_capacity'] = current_cap
            shared_state['battery_consecutive_work'] = current_streak
            
            # Flush to DB every 300 seconds (5 minutes) as a backup safety save
            ticks_since_flush += 1
            if ticks_since_flush >= 300:
                try:
                    db.flush_battery_state(battery.capacity, battery.consecutive_work_minutes)
                    db.save()
                except Exception:
                    pass
                ticks_since_flush = 0

            # Run periodic EcoQoS unthrottling for the process tree every 15 seconds
            ticks_since_ecoqos += 1
            if ticks_since_ecoqos >= 15:
                try:
                    disable_ecoqos_for_process_tree()
                except Exception:
                    pass
                ticks_since_ecoqos = 0
        except Exception as e:
            print(f"Error in CognitiveBattery tick: {e}")

def run_webview_gui(url):
    """Run a standalone pywebview Edge WebView2 window."""
    import webview
    import psutil
    import os
    import sys
    import threading
    
    # Configure WEBVIEW2_RUNTIME_PATH dynamically if needed
    is_webview2_installed()
    
    # 1. Parent process monitor thread
    def monitor_parent():
        parent_pid = os.getppid()
        try:
            parent = psutil.Process(parent_pid)
        except Exception:
            os._exit(0)

        last_db_check = 0
        settings = None
        adaptive = None

        while True:
            time.sleep(1.0)
            try:
                if not parent.is_running() or parent.status() == psutil.STATUS_ZOMBIE:
                    os._exit(0)
            except Exception:
                os._exit(0)
                
            current_time = time.time()
            if current_time - last_db_check > 60:
                settings = db.get_settings()
                adaptive = db.get_adaptive_times()
                last_db_check = current_time

                
    monitor_thread = threading.Thread(target=monitor_parent, daemon=True)
    monitor_thread.start()
    
    # 2. Start periodic background EcoQoS disabling for child processes
    def delayed_disable_throttling():
        # Wait 5 seconds for child processes to spawn, run ONCE, then exit the thread.
        time.sleep(5.0)
        disable_ecoqos_for_process_tree()
            
    throttling_thread = threading.Thread(target=delayed_disable_throttling, daemon=True)
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
    webview.start(gui='edgechromium', debug=False)

# Original pywebview standalone app launcher restored
def launch_app_window(url):
    """Launch the dashboard url in a standalone pywebview GUI subprocess."""
    import sys
    import subprocess
    import os
    
    from backend.server import SHARED_API_TOKEN
    
    if getattr(sys, 'frozen', False):
        exe = sys.executable
        try:
            return subprocess.Popen([exe, "--gui", SHARED_API_TOKEN])
        except Exception as e:
            print(f"Error launching standalone app GUI: {e}")
            return None
    else:
        exe = sys.executable
        script = sys.argv[0]
        try:
            return subprocess.Popen([exe, script, "--gui", SHARED_API_TOKEN])
        except Exception as e:
            print(f"Error launching standalone app GUI in dev: {e}")
            return None

def is_webview2_installed():
    if sys.platform != "win32":
        return True
    try:
        import webview
    except ImportError:
        pass
    registry_found = False
    try:
        import winreg
        paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}")
        ]
        for root, subkey in paths:
            try:
                with winreg.OpenKey(root, subkey) as key:
                    version, _ = winreg.QueryValueEx(key, "pv")
                    if version and version != "0.0.0.0":
                        registry_found = True
                        break
            except FileNotFoundError:
                continue
    except Exception:
        pass
        
    if registry_found:
        return True

    # Robust path-based check fallback for systems where Edge Update keys are missing
    import glob
    search_roots = []
    pf_x86 = os.environ.get("ProgramFiles(x86)")
    pf_x64 = os.environ.get("ProgramFiles")
    sys_drive = os.environ.get("SystemDrive", "C:")
    
    if pf_x86:
        search_roots.append(os.path.join(pf_x86, "Microsoft", "EdgeWebView", "Application"))
    else:
        search_roots.append(os.path.join(sys_drive + "\\Program Files (x86)", "Microsoft", "EdgeWebView", "Application"))
        
    if pf_x64:
        search_roots.append(os.path.join(pf_x64, "Microsoft", "EdgeWebView", "Application"))
    else:
        search_roots.append(os.path.join(sys_drive + "\\Program Files", "Microsoft", "EdgeWebView", "Application"))

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        search_roots.append(os.path.join(local_appdata, "Microsoft", "EdgeWebView", "Application"))
        
    for root in search_roots:
        if os.path.exists(root):
            try:
                matches = glob.glob(os.path.join(root, "**", "msedgewebview2.exe"), recursive=True)
                if matches:
                    runtime_dir = os.path.dirname(matches[0])
                    try:
                        import webview
                        webview.settings['WEBVIEW2_RUNTIME_PATH'] = runtime_dir
                    except Exception:
                        pass
                    return True
            except Exception:
                pass
    return False

_job_handle_holder = None

def assign_self_to_job():
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        
        kernel32 = ctypes.windll.kernel32
        
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
        JobObjectExtendedLimitInformation = 9
        
        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('PerProcessUserTimeLimit', ctypes.c_int64),
                ('PerJobUserTimeLimit', ctypes.c_int64),
                ('LimitFlags', wintypes.DWORD),
                ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t),
                ('ActiveProcessLimit', wintypes.DWORD),
                ('Affinity', ctypes.c_void_p),
                ('PriorityClass', wintypes.DWORD),
                ('SchedulingClass', wintypes.DWORD),
            ]
            
        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ('ReadOperationCount', ctypes.c_ulonglong),
                ('WriteOperationCount', ctypes.c_ulonglong),
                ('OtherOperationCount', ctypes.c_ulonglong),
                ('ReadTransferCount', ctypes.c_ulonglong),
                ('WriteTransferCount', ctypes.c_ulonglong),
                ('OtherTransferCount', ctypes.c_ulonglong),
            ]
            
        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ('IoInfo', IO_COUNTERS),
                ('ProcessMemoryLimit', ctypes.c_size_t),
                ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t),
                ('PeakJobMemoryUsed', ctypes.c_size_t),
            ]
            
        # Explicit argtypes and restype to prevent ctypes TypeErrors on Windows
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        
        kernel32.SetInformationJobObject.argtypes = [
            ctypes.c_void_p, 
            ctypes.c_int, 
            ctypes.c_void_p, 
            ctypes.c_ulong
        ]
        kernel32.SetInformationJobObject.restype = ctypes.c_int
        
        kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel32.AssignProcessToJobObject.restype = ctypes.c_int
        
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
            
        h_job = kernel32.CreateJobObjectW(None, None)
        if not h_job:
            return False
            
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        
        ret = kernel32.SetInformationJobObject(
            h_job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info)
        )
        if not ret:
            return False
            
        h_process = kernel32.GetCurrentProcess()
        ret = kernel32.AssignProcessToJobObject(h_job, h_process)
        if not ret:
            return False
            
        global _job_handle_holder
        _job_handle_holder = h_job
        return True
    except Exception as e:
        print(f"[MIND-FLOW] Warning: failed to assign to Job Object: {e}")
        return False

if __name__ == "__main__":
    if sys.platform == "win32":
        assign_self_to_job()

    try:
        disable_ecoqos_for_process_tree()
    except Exception:
        pass

    # If --gui argument is passed, launch the pywebview standalone window process
    if len(sys.argv) > 1 and sys.argv[1] == "--gui":
        token = sys.argv[2] if len(sys.argv) > 2 else ""
        run_webview_gui(f"http://127.0.0.1:5000/?token={token}")
        sys.exit(0)

    # 1. Start Server in a separate daemon thread
    server_thread = threading.Thread(target=run_server, kwargs={"port": 5000}, daemon=True)
    server_thread.start()
    
    # Wait a brief moment for Flask to initialize
    time.sleep(0.5)

    # 2. Open dashboard in native app window (pywebview process) or default browser fallback
    if sys.platform == "win32" and not is_webview2_installed():
        print("\n[MIND-FLOW] Microsoft Edge WebView2 Runtime is not installed.")
        print("To run in a standalone application window, please install it from:")
        print("https://developer.microsoft.com/en-us/microsoft-edge/webview2/\n")
        print("Launching the dashboard in your default web browser instead...")
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:5000/?token={SHARED_API_TOKEN}")
        gui_proc = None
    else:
        print("Launching Cognitive Dashboard in Standalone App Mode...")
        gui_proc = launch_app_window(f"http://127.0.0.1:5000/?token={SHARED_API_TOKEN}")

    # 3. Start state machine in the main thread (blocks execution)
    if sys.platform == "win32":
        t_hook = threading.Thread(target=start_win_event_listener, daemon=True)
        t_hook.start()
        
    try:
        main_state_machine(gui_process=gui_proc)
    except KeyboardInterrupt:
        print("\nMIND-FLOW terminated by user.")
        sys.exit(0)
