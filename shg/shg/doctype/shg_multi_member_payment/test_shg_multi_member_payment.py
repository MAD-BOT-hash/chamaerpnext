# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
import unittest

class TestSHGMultiMemberPayment(unittest.TestCase):
    def setUp(self):
        # Create test data
        pass

    def tearDown(self):
        # Clean up test data
        pass

    def test_get_unpaid_invoices(self):
        """Test fetching unpaid invoices"""
        # This would require setting up test data
        pass

    def test_validate_payment_method(self):
        """Test payment method validation"""
        payment = frappe.get_doc({
            "doctype": "SHG Multi Member Payment",
            "payment_method": "Not Specified"
        })
        
        with self.assertRaises(frappe.ValidationError):
            payment.insert()

    def test_calculate_totals(self):
        """Test calculation of totals"""
        payment = frappe.new_doc("SHG Multi Member Payment")
        payment.append("invoices", {
            "payment_amount": 100
        })
        payment.append("invoices", {
            "payment_amount": 200
        })
        
        payment.calculate_totals()
        
        self.assertEqual(payment.total_selected_invoices, 2)
        self.assertEqual(payment.total_payment_amount, 300)
        self.assertEqual(payment.total_amount, 300)

    def test_validate_duplicate_invoices(self):
        """Test duplicate invoice validation"""
        payment = frappe.new_doc("SHG Multi Member Payment")
        payment.append("invoices", {
            "invoice": "TEST-001"
        })
        payment.append("invoices", {
            "invoice": "TEST-001"  # Duplicate
        })
        
        with self.assertRaises(frappe.ValidationError):
            payment.validate_duplicate_invoices()

if __name__ == '__main__':
    unittest.main()