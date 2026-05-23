import subprocess
import sys

print("Starting execution of 50 test cycles...")
all_success = True
for i in range(1, 51):
    res = subprocess.run([sys.executable, "verify_tests.py"], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Cycle {i} FAILED!")
        print(res.stderr or res.stdout)
        all_success = False
        break
    else:
        if i % 10 == 0 or i == 1:
            print(f"Cycle {i}/50 completed successfully.")

if all_success:
    print("All 50 test cycles completed successfully without a single error!")
