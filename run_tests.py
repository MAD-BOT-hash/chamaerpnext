#!/usr/bin/env python3
"""
Test runner for SHG ERPNext application
"""
import os
import sys
import subprocess

def run_tests(test_pattern=None, verbose=True):
    """Run pytest with specified options"""
    cmd = ["python", "-m", "pytest"]
    
    if verbose:
        cmd.extend(["-v", "--tb=short"])
    
    if test_pattern:
        cmd.append(test_pattern)
    else:
        cmd.append("tests/")
    
    print(f"Running command: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        print(f"Exit code: {result.returncode}")
        return result.returncode == 0
    except Exception as e:
        print(f"Error running tests: {e}")
        return False

def run_specific_test(test_file):
    """Run a specific test file"""
    return run_tests(test_file)

def run_unit_tests():
    """Run unit tests only"""
    return run_tests("tests/ -m unit")

def run_integration_tests():
    """Run integration tests only"""
    return run_tests("tests/ -m integration")

def list_tests():
    """List all available tests"""
    cmd = ["python", "-m", "pytest", "--collect-only", "tests/"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        return True
    except Exception as e:
        print(f"Error listing tests: {e}")
        return False

if __name__ == "__main__":
    print("SHG ERPNext Test Runner")
    print("=" * 30)
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "list":
            list_tests()
        elif command == "unit":
            run_unit_tests()
        elif command == "integration":
            run_integration_tests()
        elif command.startswith("test_"):
            run_specific_test(f"tests/{command}")
        else:
            run_tests(command)
    else:
        # Run all tests
        run_tests()