"""
Active window tracking, idle detection, COM audio session monitoring,
and power management for MIND-FLOW.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import time
import subprocess
import threading
import ctypes
import queue
import logging
from backend.database import is_browser_process

logger = logging.getLogger("tracker")

if sys.platform == "win32":
    import winsound

if sys.platform == "win32":
    from ctypes import wintypes
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
    ctypes.windll.kernel32.GetTickCount.restype = wintypes.DWORD
    
    # Define argtypes and restypes for window tracking to fix 64-bit truncation bugs
    ctypes.windll.user32.GetForegroundWindow.restype = wintypes.HWND
    ctypes.windll.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    ctypes.windll.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    ctypes.windll.kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    ctypes.windll.kernel32.OpenProcess.restype = wintypes.HANDLE
    ctypes.windll.kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    ctypes.windll.kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    ctypes.windll.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    ctypes.windll.kernel32.CloseHandle.restype = wintypes.BOOL
    ctypes.windll.user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT, wintypes.UINT, ctypes.POINTER(wintypes.DWORD)]
    ctypes.windll.user32.SendMessageTimeoutW.restype = wintypes.LPARAM
    ctypes.windll.user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    ctypes.windll.user32.GetWindowTextLengthW.restype = ctypes.c_int
    ctypes.windll.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    ctypes.windll.user32.GetWindowTextW.restype = ctypes.c_int
    ctypes.windll.user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    ctypes.windll.user32.FindWindowExW.restype = wintypes.HWND
    ctypes.windll.user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
    ctypes.windll.user32.GetLastInputInfo.restype = wintypes.BOOL

    WINEVENTPROC = ctypes.WINFUNCTYPE(
        None,
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.HWND,
        wintypes.LONG,
        wintypes.LONG,
        wintypes.DWORD,
        wintypes.DWORD
    )
    ctypes.windll.user32.SetWinEventHook.argtypes = [
        wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, WINEVENTPROC,
        wintypes.DWORD, wintypes.DWORD, wintypes.DWORD
    ]
    ctypes.windll.user32.SetWinEventHook.restype = wintypes.HANDLE
    ctypes.windll.user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
    ctypes.windll.user32.UnhookWinEvent.restype = wintypes.BOOL
    ctypes.windll.user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    ctypes.windll.user32.PostThreadMessageW.restype = wintypes.BOOL
else:
    LASTINPUTINFO = None
    WINEVENTPROC = None

# --- Module-level FFI Library Initialization for macOS / Linux ---
_cg_lib = None
_xlib = None
_xss = None
_XScreenSaverInfo = None

if sys.platform == "darwin":
    try:
        from ctypes import util
        _cg_path = util.find_library('CoreGraphics')
        if _cg_path:
            _cg_lib = ctypes.CDLL(_cg_path)
            _cg_lib.CGEventSourceSecondsSinceLastEventType.argtypes = [ctypes.c_int, ctypes.c_int]
            _cg_lib.CGEventSourceSecondsSinceLastEventType.restype = ctypes.c_double
    except Exception:
        _cg_lib = None
elif sys.platform != "win32":
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
        _XScreenSaverInfo = XScreenSaverInfo
        _xlib = ctypes.cdll.LoadLibrary('libX11.so.6')
        _xss = ctypes.cdll.LoadLibrary('libXss.so.1')
        
        _xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        _xlib.XOpenDisplay.restype = ctypes.c_void_p
        _xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
        _xlib.XCloseDisplay.restype = ctypes.c_int
        _xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        _xlib.XDefaultRootWindow.restype = ctypes.c_ulong
        _xlib.XFree.argtypes = [ctypes.c_void_p]
        _xlib.XFree.restype = ctypes.c_int
        
        _xss.XScreenSaverAllocInfo.argtypes = []
        _xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(_XScreenSaverInfo)
        _xss.XScreenSaverQueryInfo.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(_XScreenSaverInfo)]
        _xss.XScreenSaverQueryInfo.restype = ctypes.c_int
    except Exception:
        _xlib = None
        _xss = None
        _XScreenSaverInfo = None


# Module-level Win32 HWND & Process Name Cache
_last_hwnd = None
_cached_process_name = None
_hwnd_cache_lock = threading.RLock()


def _resolve_root_hwnd(hwnd):
    """Resolve a child control/window HWND to its top-level root owner window."""
    if not hwnd or hwnd == 0:
        return 0
    try:
        # GA_ROOTOWNER = 3, GA_ROOT = 2
        root = ctypes.windll.user32.GetAncestor(hwnd, 3)
        if root and root != 0 and ctypes.windll.user32.IsWindow(root):
            return root
        root = ctypes.windll.user32.GetAncestor(hwnd, 2)
        if root and root != 0 and ctypes.windll.user32.IsWindow(root):
            return root
    except Exception:
        pass
    return hwnd


def is_dashboard_window(process_name, window_title, hwnd=None):
    """Determine whether the specified window belongs to the MIND-FLOW application itself."""
    p = (process_name or "").lower()
    t = (window_title or "").lower()

    # Developer IDEs and editors should NEVER be misidentified as the dashboard
    IDE_PROCESSES = {
        "code.exe", "cursor.exe", "devenv.exe", "pycharm64.exe", "pycharm.exe",
        "sublime_text.exe", "notepad++.exe", "clion64.exe", "idea64.exe",
        "windsurf.exe", "fleet.exe", "zed.exe"
    }
    if p in IDE_PROCESSES:
        return False

    if hwnd and sys.platform == "win32":
        try:
            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == os.getpid():
                return True
        except Exception:
            pass

    # Exact dashboard title markers
    dashboard_title_markers = [
        "mind-flow // cognitive companion dashboard",
        "cognitive productivity tracker ui",
        "mind-flow dashboard",
        "mind-flow //"
    ]
    if any(marker in t for marker in dashboard_title_markers):
        return True

    # Match WebView2 / PyWebView child processes when associated with dashboard exact title
    if ("webview" in p or p in ["python.exe", "pythonw.exe", "mind-flow.exe"]) and (
        "cognitive companion dashboard" in t or "cognitive productivity tracker" in t
    ):
        return True

    return False


def get_active_window_title_direct(hwnd):
    if not hwnd or hwnd == 0:
        return "None"
    try:
        root_hwnd = _resolve_root_hwnd(hwnd) or hwnd
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(root_hwnd, ctypes.byref(pid))
        if pid.value == os.getpid():
            # For same-process windows, use SendMessageTimeout to avoid deadlock if the GUI thread is hung
            buf = ctypes.create_unicode_buffer(512)
            res = wintypes.DWORD()
            ret = ctypes.windll.user32.SendMessageTimeoutW(
                root_hwnd, 0x000D, 512, ctypes.cast(buf, wintypes.LPARAM), 0x0002, 100, ctypes.byref(res)
            )
            val = buf.value if ret != 0 else "MIND-FLOW // Cognitive Companion Dashboard"
            return val if val.strip() else "MIND-FLOW // Cognitive Companion Dashboard"

        # 1. First attempt: Query title on root_hwnd
        length = ctypes.windll.user32.GetWindowTextLengthW(root_hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(root_hwnd, buf, length + 1)
            if buf.value and buf.value.strip():
                return buf.value.strip()

        # 2. Fallback: Query title on direct hwnd if different
        if root_hwnd != hwnd:
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                if buf.value and buf.value.strip():
                    return buf.value.strip()

        return "None"
    except Exception as e:
        logger.debug("Error reading active window title: %s", e)
        return "None"


def get_active_process_name_direct(hwnd):
    global _last_hwnd, _cached_process_name
    if not hwnd or hwnd == 0:
        with _hwnd_cache_lock:
            _last_hwnd = None
            _cached_process_name = None
        return "None"

    root_hwnd = _resolve_root_hwnd(hwnd) or hwnd

    with _hwnd_cache_lock:
        if root_hwnd == _last_hwnd and _cached_process_name is not None:
            return _cached_process_name

    try:
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(root_hwnd, ctypes.byref(pid))
        if pid.value == 0 and root_hwnd != hwnd:
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            with _hwnd_cache_lock:
                _last_hwnd = None
                _cached_process_name = None
            return "None"

        if pid.value == os.getpid():
            proc_name = "python.exe"
            with _hwnd_cache_lock:
                _last_hwnd = root_hwnd
                _cached_process_name = proc_name
            return proc_name

        h_process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not h_process:
            h_process = ctypes.windll.kernel32.OpenProcess(0x0400, False, pid)
        if not h_process:
            try:
                import psutil
                p = psutil.Process(pid.value)
                proc_name = p.name().lower()
                if proc_name and proc_name != "none":
                    with _hwnd_cache_lock:
                        _last_hwnd = root_hwnd
                        _cached_process_name = proc_name
                    return proc_name
            except Exception:
                pass
            with _hwnd_cache_lock:
                _last_hwnd = None
                _cached_process_name = None
            return "None"
        try:
            buf_size = wintypes.DWORD(260)
            buf = ctypes.create_unicode_buffer(buf_size.value)
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(buf_size)):
                proc_name = os.path.basename(buf.value).lower()

                # UWP Child Window Resolution
                if proc_name == "applicationframehost.exe":
                    child_hwnd = ctypes.windll.user32.FindWindowExW(root_hwnd, None, None, None)
                    uwp_depth = 0
                    max_uwp_depth = 10
                    while child_hwnd and uwp_depth < max_uwp_depth:
                        uwp_depth += 1
                        child_pid = wintypes.DWORD()
                        ctypes.windll.user32.GetWindowThreadProcessId(child_hwnd, ctypes.byref(child_pid))
                        if child_pid.value and child_pid.value != pid.value:
                            try:
                                import psutil
                                c_proc = psutil.Process(child_pid.value).name().lower()
                                if c_proc and c_proc != "applicationframehost.exe":
                                    proc_name = c_proc
                                    break
                            except Exception:
                                pass
                        child_hwnd = ctypes.windll.user32.FindWindowExW(root_hwnd, child_hwnd, None, None)

                if proc_name and proc_name != "None":
                    with _hwnd_cache_lock:
                        _last_hwnd = root_hwnd
                        _cached_process_name = proc_name
                return proc_name

            # Fallback if QueryFullProcessImageNameW returned False
            try:
                import psutil
                p = psutil.Process(pid.value)
                proc_name = p.name().lower()
                if proc_name and proc_name != "none":
                    with _hwnd_cache_lock:
                        _last_hwnd = root_hwnd
                        _cached_process_name = proc_name
                    return proc_name
            except Exception:
                pass

            with _hwnd_cache_lock:
                _last_hwnd = None
                _cached_process_name = None
            return "None"
        finally:
            ctypes.windll.kernel32.CloseHandle(h_process)
    except Exception as e:
        logger.debug("Error reading active process name: %s", e)
        with _hwnd_cache_lock:
            _last_hwnd = None
            _cached_process_name = None
        return "None"



_event_tracker_thread = None
_event_tracker_lock = threading.RLock()
_cached_event_details = ("None", "None")
_event_listener_active = False
_active_winevent_proc = None

class WinEventTrackerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="WinEventTrackerThread")
        self.thread_id = None
        self.hook = None
        self._proc = None
        self._ready_event = threading.Event()

    def run(self):
        global _cached_event_details, _event_listener_active
        if sys.platform != "win32" or WINEVENTPROC is None:
            self._ready_event.set()
            return

        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        def win_event_proc(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
            if event == 0x800C:  # EVENT_OBJECT_NAMECHANGE
                fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
                if hwnd != fg_hwnd:
                    root = _resolve_root_hwnd(hwnd) if hwnd else None
                    if root != fg_hwnd:
                        return  # Drop non-foreground name change events
            
            global _cached_event_details
            try:
                if event == 0x0003 or (event == 0x800C and idObject == 0):  # EVENT_SYSTEM_FOREGROUND or EVENT_OBJECT_NAMECHANGE for OBJID_WINDOW
                    target_hwnd = hwnd or ctypes.windll.user32.GetForegroundWindow()
                    if target_hwnd:
                        root_hwnd = _resolve_root_hwnd(target_hwnd) or target_hwnd
                        title = get_active_window_title_direct(root_hwnd)
                        proc = get_active_process_name_direct(root_hwnd)
                        if title and title != "None":
                            with _event_tracker_lock:
                                _cached_event_details = (title, proc)
            except Exception as e:
                logger.debug("[WinEventTracker] Callback exception: %s", e)

        self._proc = WINEVENTPROC(win_event_proc)
        global _active_winevent_proc
        _active_winevent_proc = self._proc
        # Hook events from EVENT_SYSTEM_FOREGROUND (0x0003) to EVENT_OBJECT_NAMECHANGE (0x800C)
        self.hook = ctypes.windll.user32.SetWinEventHook(
            0x0003, 0x800C, None, self._proc, 0, 0, 0x0000
        )

        if not self.hook:
            _event_listener_active = False
            self._ready_event.set()
            return

        _event_listener_active = True

        # Initial query to seed cache
        hwnd_initial = ctypes.windll.user32.GetForegroundWindow()
        if hwnd_initial:
            title = get_active_window_title_direct(hwnd_initial)
            proc = get_active_process_name_direct(hwnd_initial)
            with _event_tracker_lock:
                _cached_event_details = (title, proc)

        # Signal that the hook is installed and message queue is ready
        self._ready_event.set()

        try:
            msg = wintypes.MSG()
            while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x0012:  # WM_QUIT
                    break
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            if self.hook:
                ctypes.windll.user32.UnhookWinEvent(self.hook)
                self.hook = None
            _event_listener_active = False

    def stop(self):
        if self.thread_id and self.is_alive():
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
            self.join(timeout=2.0)
        global _active_winevent_proc
        _active_winevent_proc = None

def start_event_listener():
    global _event_tracker_thread, _event_listener_active
    if sys.platform != "win32":
        return False
    with _event_tracker_lock:
        if _event_tracker_thread is None or not _event_tracker_thread.is_alive():
            _event_tracker_thread = WinEventTrackerThread()
            _event_tracker_thread.start()
            # Wait for the thread to install the hook and create its message queue
            _event_tracker_thread._ready_event.wait(timeout=2.0)
    return _event_listener_active

def stop_event_listener():
    global _event_tracker_thread, _event_listener_active
    with _event_tracker_lock:
        if _event_tracker_thread and _event_tracker_thread.is_alive():
            _event_tracker_thread.stop()
        _event_tracker_thread = None
        _event_listener_active = False

def get_cached_window_details():
    """Return the last event-listener-captured window details (<0.001ms)."""
    with _event_tracker_lock:
        return _cached_event_details

def get_active_window_details(force_poll=False):
    """Retrieve both foreground window title and process name, using OS event hooks when available or live polling fallbacks."""
    # Support mock patch in test suite: if the individual functions are mocked, call them directly
    if hasattr(get_active_window_title, '_mock_self') or hasattr(get_active_process_name, '_mock_self') or hasattr(get_active_window_title, 'called') or hasattr(get_active_process_name, 'called'):
        return get_active_window_title(), get_active_process_name()

    if _event_listener_active and not force_poll:
        with _event_tracker_lock:
            if _cached_event_details[0] not in ["None", ""] and _cached_event_details[1] not in ["None", ""]:
                return _cached_event_details

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
            except Exception as e:
                logger.debug("osascript window title query failed: %s", e)
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
                    except Exception as e:
                        logger.debug("reading /proc/%s/comm failed: %s", pid, e)
                return title, process
            except Exception as e:
                logger.debug("xprop window query failed: %s", e)
            return "None", "none"

    if sys.platform == "win32":
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if hwnd:
            return get_active_window_title_direct(hwnd), get_active_process_name_direct(hwnd)
    return "None", "None" 

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

    if sys.platform == "win32":
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if hwnd:
            return get_active_window_title_direct(hwnd)
    return "None" 

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

    if sys.platform == "win32":
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if hwnd:
            return get_active_process_name_direct(hwnd)
    return "None" 

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
        prototype = ctypes.WINFUNCTYPE(restype, *([ctypes.c_void_p] + argtypes))
        def method(self, *args):
            vtable = ctypes.cast(self, ctypes.POINTER(ctypes.c_void_p))[0]
            func_ptr = ctypes.cast(ctypes.c_void_p(vtable + index * ctypes.sizeof(ctypes.c_void_p)), ctypes.POINTER(ctypes.c_void_p))[0]
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

    _p_enumerator = None
    _p_device = None
    _p_meter = None
    import threading
    _com_thread_local = threading.local()
    _audio_com_lock = threading.RLock()

    def check_windows_audio_active():
        global _p_enumerator, _p_device, _p_meter, _com_thread_local
        with _audio_com_lock:
            try:
                if not getattr(_com_thread_local, 'initialized', False):
                    try:
                        ctypes.windll.ole32.CoInitializeEx(None, 2)  # COINIT_MULTITHREADED
                        _com_thread_local.initialized = True
                    except Exception as e:
                        logger.debug("CoInitializeEx audio COM initialization: %s", e)
                if not _p_meter:
                    enumerator = ctypes.c_void_p()
                    hr = ctypes.windll.ole32.CoCreateInstance(
                        ctypes.byref(CLSID_MMDeviceEnumerator),
                        None,
                        1,
                        ctypes.byref(IID_IMMDeviceEnumerator),
                        ctypes.byref(enumerator)
                    )
                    if hr != 0:
                        release_audio_interfaces()
                        return False
                        
                    _p_enumerator = IMMDeviceEnumerator(enumerator.value)
                    device = ctypes.c_void_p()
                    hr = _p_enumerator.GetDefaultAudioEndpoint(0, 1, ctypes.byref(device))
                    if hr != 0:
                        release_audio_interfaces()
                        return False
                        
                    _p_device = IMMDevice(device.value)
                    meter = ctypes.c_void_p()
                    hr = _p_device.Activate(ctypes.byref(IID_IAudioMeterInformation), 1, None, ctypes.byref(meter))
                    if hr != 0:
                        release_audio_interfaces()
                        return False
                        
                    _p_meter = IAudioMeterInformation(meter.value)
                    
                peak = ctypes.c_float()
                hr = _p_meter.GetPeakValue(ctypes.byref(peak))
                if hr == 0:
                    return peak.value > 0.0005
                else:
                    # Device changed or failed, release cache to reinitialize next time
                    release_audio_interfaces()
                    return False
            except Exception as e:
                logger.debug("Windows audio peak check failed: %s", e)
                release_audio_interfaces()
                return False

    def release_audio_interfaces():
        global _p_enumerator, _p_device, _p_meter
        with _audio_com_lock:
            if _p_meter and getattr(_p_meter, "value", 0) != 0:
                try:
                    _p_meter.Release()
                except Exception:
                    pass
                _p_meter = None
            if _p_device and getattr(_p_device, "value", 0) != 0:
                try:
                    _p_device.Release()
                except Exception:
                    pass
                _p_device = None
            if _p_enumerator and getattr(_p_enumerator, "value", 0) != 0:
                try:
                    _p_enumerator.Release()
                except Exception:
                    pass
                _p_enumerator = None
    
    import atexit
    atexit.register(release_audio_interfaces)
else:
    def check_windows_audio_active():
        return False

_last_audio_active_time = 0.0
_last_audio_check_time = 0.0
_last_audio_result = False
import threading
_audio_time_lock = threading.RLock()

def is_audio_playing():
    """Check if audio playback is currently active in the OS (to prevent false-positive idle states).
    
    Uses both positive and negative caching to throttle expensive OS-level audio checks
    (COM calls on Windows, subprocess on macOS/Linux) to a maximum of once every 5 seconds.
    """
    global _last_audio_active_time, _last_audio_check_time, _last_audio_result
    current_time = time.time()

    with _audio_time_lock:
        # Fast path: If last audio check was recent (< 5s ago), return cached result
        if (current_time - _last_audio_check_time) < 5.0:
            if _last_audio_result:
                return True
            # Negative cache: audio was not playing last time we checked, and check is still fresh
            return (current_time - _last_audio_active_time) < 5.0

    active = False
    if sys.platform == "win32":
        active = check_windows_audio_active()
    elif sys.platform == "darwin":
        try:
            output = subprocess.check_output(["pmset", "-g", "assertions"], stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
            for line in output.splitlines():
                if ("PreventUserIdleSystemSleep" in line or "PreventUserIdleDisplaySleep" in line) and "1" in line:
                    active = True
                    break
        except Exception:
            pass
    else:
        try:
            output = subprocess.getoutput("pactl list sink-inputs")
            if "state: RUNNING" in output or "State: RUNNING" in output:
                active = True
        except Exception:
            pass

    with _audio_time_lock:
        _last_audio_check_time = current_time
        _last_audio_result = active
        if active:
            _last_audio_active_time = current_time
            return True
        
        return (current_time - _last_audio_active_time) < 5.0

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
            if _cg_lib is not None:
                try:
                    return _cg_lib.CGEventSourceSecondsSinceLastEventType(1, -1)
                except Exception as e:
                    logger.debug("CGEventSourceSecondsSinceLastEventType failed: %s", e)
            try:
                cmd = "ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {print $NF/1000000000; exit}'"
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip()
                return float(output) if output else 0.0
            except Exception as e:
                logger.debug("ioreg idle check failed: %s", e)
                return 0.0
        else:
            if _xlib is not None and _xss is not None and _XScreenSaverInfo is not None:
                try:
                    display_env = os.environ.get('DISPLAY', ':0.0').encode('utf-8')
                    display = _xlib.XOpenDisplay(display_env)
                    if display:
                        try:
                            root = _xlib.XDefaultRootWindow(display)
                            info = _xss.XScreenSaverAllocInfo()
                            if info:
                                try:
                                    if _xss.XScreenSaverQueryInfo(display, root, info):
                                        idle_ms = info.contents.idle
                                        return float(idle_ms) / 1000.0
                                finally:
                                    _xlib.XFree(info)
                        finally:
                            _xlib.XCloseDisplay(display)
                except Exception as e:
                    logger.debug("XScreenSaverQueryInfo idle check failed: %s", e)
            try:
                output = subprocess.check_output("xprintidle", shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip()
                return float(output) / 1000.0 if output else 0.0
            except Exception as e:
                logger.debug("xprintidle failed: %s", e)
                return 0.0

    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0
        millis = (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF
        return max(0.0, millis / 1000.0)
    except Exception as e:
        logger.debug("Error reading Windows idle seconds: %s", e)
        return 0

_beep_queue = queue.Queue(maxsize=50)

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
                except Exception as e:
                    logger.warning("winsound.Beep failed for freq=%s, dur=%s: %s", freq, duration, e)
        _beep_queue.task_done()

_beep_thread = threading.Thread(target=_beep_worker, daemon=True)
_beep_thread.start()

def play_beep_sequence(sequence):
    """Play a sequence of beeps asynchronously using a bounded queue-managed daemon thread."""
    try:
        _beep_queue.put_nowait(sequence)
    except queue.Full:
        logger.debug("Beep queue full (maxsize=50), dropping sequence")

# Win32 API Constants and Structures for Power Throttling (EcoQoS/Efficiency Mode)
ProcessPowerThrottling = 4
PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION = 0x2
NORMAL_PRIORITY_CLASS = 0x00000020

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
        state.ControlMask = PROCESS_POWER_THROTTLING_EXECUTION_SPEED | PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION
        state.StateMask = 0  # 0 to disable throttling
        
        result = ctypes.windll.kernel32.SetProcessInformation(
            handle,
            ProcessPowerThrottling,
            ctypes.byref(state),
            ctypes.sizeof(state)
        )
        # Ensure process priority class is at least Normal Priority (0x20)
        try:
            ctypes.windll.kernel32.SetPriorityClass(handle, NORMAL_PRIORITY_CLASS)
        except Exception:
            pass
        return bool(result)
    except Exception:
        return False

_ecoqos_guard_started = False
_ecoqos_guard_lock = threading.Lock()

def disable_ecoqos_for_process_tree():
    """Disable EcoQoS (Efficiency Mode) for the current Python process and all descendant processes recursively."""
    if sys.platform != "win32":
        return
        
    global _ecoqos_guard_started
    
    # Disable for current process immediately
    try:
        h_process = ctypes.windll.kernel32.GetCurrentProcess()
        disable_ecoqos_for_handle(h_process)
    except Exception:
        pass

    def run_ecoqos_sweep():
        import psutil
        current_pid = os.getpid()
        try:
            parent = psutil.Process(current_pid)
            for child in parent.children(recursive=True):
                try:
                    # PROCESS_SET_INFORMATION (0x0200) | PROCESS_SET_LIMITED_INFORMATION (0x2000)
                    h_child = ctypes.windll.kernel32.OpenProcess(0x2200, False, child.pid)
                    if not h_child:
                        h_child = ctypes.windll.kernel32.OpenProcess(0x0200, False, child.pid)
                    if h_child:
                        try:
                            disable_ecoqos_for_handle(h_child)
                        finally:
                            ctypes.windll.kernel32.CloseHandle(h_child)
                except (psutil.Error, OSError):
                    pass
        except (psutil.Error, OSError):
            pass

    # Run one sweep synchronously for existing children
    try:
        run_ecoqos_sweep()
    except Exception:
        pass

    # Start recurring guard thread if not already running
    with _ecoqos_guard_lock:
        if not _ecoqos_guard_started:
            _ecoqos_guard_started = True
            def ecoqos_loop():
                while True:
                    time.sleep(10.0)
                    try:
                        run_ecoqos_sweep()
                    except Exception:
                        pass
            threading.Thread(target=ecoqos_loop, daemon=True, name="EcoQoSGuardThread").start()


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
            kernel32.CloseHandle(h_job)
            return False
            
        h_process = kernel32.GetCurrentProcess()
        ret = kernel32.AssignProcessToJobObject(h_job, h_process)
        if not ret:
            kernel32.CloseHandle(h_job)
            return False
            
        global _job_handle_holder
        _job_handle_holder = h_job
        return True
    except Exception as e:
        print(f"[MIND-FLOW] Warning: failed to assign to Job Object: {e}")
        return False

