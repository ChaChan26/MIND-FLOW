import os
import subprocess
import sys

def build_exe():
    print("MIND-FLOW packaging automation starting...")
    
    # 1. Ensure pyinstaller is installed
    try:
        import PyInstaller
        print("PyInstaller is already installed.")
    except ImportError:
        print("PyInstaller not found. Installing now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # 2. Setup build command
    # --onefile: bundle everything into a single executable
    # --name MIND-FLOW: output name is MIND-FLOW.exe
    # --add-data: bundle static and templates folders (format is SOURCE;DEST on Windows)
    # --noconsole: hide the command window for clean desktop experience
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name", "MIND-FLOW",
        "--add-data", "static;static",
        "--add-data", "templates;templates",
        "--noconsole",
        "app.py"
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    
    # 3. Execute PyInstaller build
    try:
        subprocess.check_call(cmd)
        print("\nSUCCESS! Packaging complete.")
        print("The standalone executable has been built inside: C:\\MIND\\dist\\MIND-FLOW.exe")
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Packaging failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_exe()
