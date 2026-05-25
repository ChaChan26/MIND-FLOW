import os
import sys
import unittest

# Import the test classes from verify_tests
from verify_tests import (
    TestMindFlowComponents,
    TestMindFlowAPI,
    TestAppWindowLaunch,
    TestLockoutOverlay,
    TestMainStateMachine
)

print("Starting execution of 50 in-process test cycles...")
all_success = True

loader = unittest.TestLoader()

# Use devnull to suppress the standard unittest progress dots/output for a clean console
with open(os.devnull, "w") as devnull:
    runner = unittest.TextTestRunner(stream=devnull, verbosity=0)
    
    for i in range(1, 51):
        # Recreate the suite on every iteration to avoid 'NoneType' object is not callable (Python 3.11+ cleans up tests after running a suite)
        suite = unittest.TestSuite([
            loader.loadTestsFromTestCase(TestMindFlowComponents),
            loader.loadTestsFromTestCase(TestMindFlowAPI),
            loader.loadTestsFromTestCase(TestAppWindowLaunch),
            loader.loadTestsFromTestCase(TestLockoutOverlay),
            loader.loadTestsFromTestCase(TestMainStateMachine)
        ])
        
        result = runner.run(suite)
        if not result.wasSuccessful():
            print(f"Cycle {i} FAILED!")
            # Show details of failures
            for failure in result.failures + result.errors:
                print(failure[0], failure[1])
            all_success = False
            break
        else:
            if i % 10 == 0 or i == 1:
                print(f"Cycle {i}/50 completed successfully.")

if all_success:
    print("All 50 test cycles completed successfully without a single error!")
