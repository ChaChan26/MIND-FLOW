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
    pyinstaller_bin = os.path.join(os.path.dirname(sys.executable), "pyinstaller")
    if sys.platform == "win32" and not pyinstaller_bin.endswith(".exe"):
        pyinstaller_bin += ".exe"
    if not os.path.exists(pyinstaller_bin):
        pyinstaller_bin = "pyinstaller"

    sep = os.pathsep
    cmd = [
        pyinstaller_bin,
        "--clean",
        "--onedir",
        "--name", "MIND-FLOW",
        "--add-data", f"static{sep}static",
        "--add-data", f"templates{sep}templates",
        "--noconsole",
        "app.py"
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    
    # 3. Execute PyInstaller build
    try:
        subprocess.check_call(cmd)
        print("\nSUCCESS! Packaging complete.")
        output_dir = os.path.abspath(os.path.join("dist", "MIND-FLOW"))
        print(f"The packaged app directory has been built inside: {output_dir}")
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Packaging failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_exe()
