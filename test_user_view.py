import sys
import os
import time
import threading
import webbrowser

# Add current directory to path to ensure backend modules can be found
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.server import run_server

def main():
    print("==================================================")
    print("   Starting MIND-FLOW Cognitive Dashboard Server   ")
    print("==================================================")
    
    # 1. Start Server in a separate daemon thread
    server_thread = threading.Thread(target=run_server, kwargs={"port": 5000}, daemon=True)
    server_thread.start()
    
    # Wait a brief moment for Flask to initialize
    time.sleep(1.0)
    
    print("\nServer is running on http://127.0.0.1:5000")
    print("Opening your default browser to view the app...")
    
    # 2. Open dashboard in default browser
    webbrowser.open("http://127.0.0.1:5000")
    
    print("\nPress Ctrl+C to terminate the test and stop the server.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nTest stopped. Exiting cleanly.")
        sys.exit(0)

if __name__ == "__main__":
    main()
