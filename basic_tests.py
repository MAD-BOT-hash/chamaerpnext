#!/usr/bin/env python3
"""
Basic test runner using unittest framework
"""
import unittest
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestSHGEnvironment(unittest.TestCase):
    """Test basic SHG environment setup"""
    
    def test_import_shg(self):
        """Test that SHG module can be imported"""
        try:
            import shg
            self.assertIsNotNone(shg)
        except ImportError:
            self.fail("Failed to import SHG module")
    
    def test_shg_version(self):
        """Test that SHG has version information"""
        import shg
        self.assertTrue(hasattr(shg, '__version__'))
        self.assertIsInstance(shg.__version__, str)

class TestSHGModules(unittest.TestCase):
    """Test individual SHG modules"""
    
    def test_hooks_import(self):
        """Test hooks module import"""
        try:
            from shg import hooks
            self.assertIsNotNone(hooks)
        except ImportError:
            self.skipTest("hooks module not available")
    
    def test_install_import(self):
        """Test install module import"""
        try:
            from shg import install
            self.assertIsNotNone(install)
        except ImportError:
            self.skipTest("install module not available")

def run_basic_tests():
    """Run basic tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSHGEnvironment))
    suite.addTests(loader.loadTestsFromTestCase(TestSHGModules))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    print("Running Basic SHG Tests")
    print("=" * 30)
    
    success = run_basic_tests()
    
    print("=" * 30)
    print("Test Results:", "PASSED" if success else "FAILED")
    sys.exit(0 if success else 1)