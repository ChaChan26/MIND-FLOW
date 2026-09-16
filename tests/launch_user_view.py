"""
Test suite for MIND-FLOW Cognitive Productivity Tracker.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import unittest

os.environ["MINDFLOW_DB_FILE"] = ":memory:"
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import sys
import os
import time
import threading
import webbrowser
import socket

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

# Add current directory to path to ensure backend modules can be found
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.server import run_server

def main():
    print("==================================================")
    print("   Starting MIND-FLOW Cognitive Dashboard Server   ")
    print("==================================================")
    
    # 1. Start Server in a separate daemon thread
    port = get_free_port()
    server_thread = threading.Thread(target=run_server, kwargs={"port": port}, daemon=True)
    server_thread.start()
    
    # Wait a brief moment for Flask to initialize
    time.sleep(1.0)
    
    print(f"\nServer is running on http://127.0.0.1:{port}")
    print("Opening your default browser to view the app...")
    
    # 2. Open dashboard in default browser
    webbrowser.open(f"http://127.0.0.1:{port}")
    
    print("\nPress Ctrl+C to terminate the test and stop the server.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nTest stopped. Exiting cleanly.")
        sys.exit(0)

if __name__ == "__main__":
    main()
