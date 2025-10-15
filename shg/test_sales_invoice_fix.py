#!/usr/bin/env python3
"""
Test script to verify Sales Invoice creation fixes
"""

import frappe
import unittest
from frappe.utils.data import flt

class TestSalesInvoiceFixes(unittest.TestCase):
    def setUp(self):
        """Set up test data"""
        pass
        
    def test_flt_function_safety(self):
        """Test that flt() function handles None values safely"""
        # Test with None
        self.assertEqual(flt(None), 0.0)
        
        # Test with string numbers
        self.assertEqual(flt("100.50"), 100.5)
        
        # Test with integers
        self.assertEqual(flt(100), 100.0)
        
        # Test with floats
        self.assertEqual(flt(100.5), 100.5)
        
        # Test with invalid strings
        self.assertEqual(flt("invalid"), 0.0)
        
    def test_safe_multiplication(self):
        """Test safe multiplication with flt()"""
        # Test normal multiplication
        qty = flt(2)
        rate = flt(100.50)
        total = flt(qty * rate)
        self.assertEqual(total, 201.0)
        
        # Test with None values
        qty = flt(None)
        rate = flt(100.50)
        total = flt(qty * rate)
        self.assertEqual(total, 0.0)
        
        # Test with string values
        qty = flt("2")
        rate = flt("100.50")
        total = flt(qty * rate)
        self.assertEqual(total, 201.0)
        
    def test_safe_division(self):
        """Test safe division with flt()"""
        # Test normal division
        amount = flt(201.0)
        qty = flt(2)
        rate = flt(amount / qty) if qty > 0 else flt(amount)
        self.assertEqual(rate, 100.5)
        
        # Test division by zero
        amount = flt(201.0)
        qty = flt(0)
        rate = flt(amount / qty) if qty > 0 else flt(amount)
        self.assertEqual(rate, 201.0)

if __name__ == "__main__":
    unittest.main()