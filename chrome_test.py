import subprocess
import time
import os
import sys

def find_chrome_path():
    import winreg
    import shutil
    # 1. Search Registry
    for hkey in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hkey, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                val, _ = winreg.QueryValueEx(key, "")
                if val and os.path.exists(val):
                    return val
        except OSError:
            pass

    # 2. Check shutil.which
    path = shutil.which("chrome") or shutil.which("chrome.exe")
    if path and os.path.exists(path):
        return path

    # 3. Check standard paths
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for p in [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]:
        if p:
            paths.append(os.path.join(p, "Google", "Chrome", "Application", "chrome.exe"))
            paths.append(os.path.join(p, "Chromium", "Application", "chrome.exe"))

    for p in paths:
        if os.path.exists(p):
            return p

    return None

def test_frontend():
    print("Starting Flask server...")
    flask_proc = subprocess.Popen([sys.executable, "app.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    
    # Extract dynamically generated API Token from Flask process stdout
    token = ""
    start_time = time.time()
    while time.time() - start_time < 5.0:
        line = flask_proc.stdout.readline()
        if not line:
            break
        if "API Token:" in line:
            token = line.split("API Token:")[1].strip()
            break
        time.sleep(0.05)
        
    chrome_path = find_chrome_path()
    if not chrome_path:
        flask_proc.terminate()
        print("Error: Could not find Chrome/Chromium application!")
        sys.exit(1)
        
    print(f"Launching headless Chrome at {chrome_path} to test frontend...")
    
    # Chrome flags to run headlessly and pipe console output to stderr
    cmd = [
        chrome_path,
        "--headless",
        "--disable-gpu",
        "--enable-logging",
        "--log-level=0",
        f"http://127.0.0.1:5000/?token={token}"
    ]
    
    chrome_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Read Chrome's stderr/stdout for 5 seconds to capture console errors
    start_time = time.time()
    errors = []
    console_logs = []
    
    # Non-blocking read or small sleep then read
    time.sleep(5.0)
    
    # Terminate chrome and flask
    chrome_proc.terminate()
    flask_proc.terminate()
    
    stdout, stderr = chrome_proc.communicate()
    
    print("--- CHROME STDERR ---")
    stderr_text = stderr.decode('utf-8', errors='ignore')
    print(stderr_text)
    
    print("--- CHROME STDOUT ---")
    stdout_text = stdout.decode('utf-8', errors='ignore')
    print(stdout_text)

if __name__ == "__main__":
    test_frontend()
