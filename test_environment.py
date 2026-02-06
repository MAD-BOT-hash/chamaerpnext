#!/usr/bin/env python3
"""
Simple test to verify the testing environment
"""
import sys
import os

def test_environment():
    """Test basic environment setup"""
    print("Python version:", sys.version)
    print("Current working directory:", os.getcwd())
    
    # Test importing shg module
    try:
        import shg
        print("✅ SHG module imported successfully")
        print("SHG version:", getattr(shg, '__version__', 'Unknown'))
    except ImportError as e:
        print("❌ Failed to import SHG module:", e)
        return False
    
    # Test importing pytest
    try:
        import pytest
        print("✅ pytest imported successfully")
        print("pytest version:", pytest.__version__)
    except ImportError as e:
        print("❌ Failed to import pytest:", e)
        return False
    
    # Test importing frappe (if available)
    try:
        import frappe
        print("✅ frappe imported successfully")
    except ImportError:
        print("⚠️ frappe not available (expected in development environment)")
    
    return True

if __name__ == "__main__":
    print("Environment Test for SHG ERPNext")
    print("=" * 40)
    success = test_environment()
    print("=" * 40)
    print("Environment test:", "PASSED" if success else "FAILED")