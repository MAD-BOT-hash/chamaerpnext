# Copyright (c) 2026, SHG Solutions
# License: MIT

import frappe
import unittest
from frappe.utils import today, flt


class TestSHGMultiMemberLoanRepayment(unittest.TestCase):
    def setUp(self):
        """Set up test data"""
        # Create test company if it doesn't exist
        if not frappe.db.exists("Company", "Test Company"):
            company = frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "abbr": "TC",
                "default_currency": "KES"
            })
            company.insert()
        
        # Create test member
        if not frappe.db.exists("SHG Member", "TEST-MEMBER-001"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_id": "TEST-MEMBER-001",
                "member_name": "Test Member One",
                "phone_number": "1234567890",
                "id_number": "12345678",
                "membership_status": "Active"
            })
            member.insert()
        
        # Create test loan type
        if not frappe.db.exists("SHG Loan Type", "Test Personal Loan"):
            loan_type = frappe.get_doc({
                "doctype": "SHG Loan Type",
                "loan_type_name": "Test Personal Loan",
                "description": "Test personal loan for testing",
                "interest_rate": 12,
                "interest_type": "Reducing Balance",
                "default_tenure_months": 12,
                "penalty_rate": 5,
                "repayment_frequency": "Monthly",
                "minimum_amount": 1000,
                "maximum_amount": 100000,
                "enabled": 1
            })
            loan_type.insert()
        
        # Create test loan
        if not frappe.db.exists("SHG Loan", "TEST-LOAN-001"):
            loan = frappe.get_doc({
                "doctype": "SHG Loan",
                "member": "TEST-MEMBER-001",
                "member_name": "Test Member One",
                "loan_type": "Test Personal Loan",
                "loan_amount": 10000,
                "interest_rate": 12,
                "interest_type": "Flat Rate",
                "loan_period_months": 12,
                "repayment_frequency": "Monthly",
                "application_date": today(),
                "disbursement_date": today(),
                "status": "Disbursed",
                "company": "Test Company"
            })
            loan.insert()
            loan.submit()
    
    def tearDown(self):
        """Clean up test data"""
        # Note: In a real implementation, you would want to clean up test data
        # For now, we'll leave it for inspection
        pass
    
    def test_get_members_with_active_loans(self):
        """Test fetching members with active loans"""
        result = frappe.call(
            "shg.shg.doctype.shg_multi_member_loan_repayment.shg_multi_member_loan_repayment.get_members_with_active_loans",
            company="Test Company"
        )
        
        # Should return at least one member with active loan
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        
        # Check that the returned data has required fields
        loan_data = result[0]
        self.assertIn("member", loan_data)
        self.assertIn("member_name", loan_data)
        self.assertIn("loan", loan_data)
        self.assertIn("loan_type", loan_data)
        self.assertIn("outstanding_balance", loan_data)
        
        # Outstanding balance should be greater than 0
        self.assertGreater(flt(loan_data["outstanding_balance"]), 0)
    
    def test_validate_payment_amounts(self):
        """Test payment amount validation"""
        # Create test document
        repayment = frappe.new_doc("SHG Multi Member Loan Repayment")
        repayment.repayment_date = today()
        repayment.company = "Test Company"
        repayment.payment_method = "Cash"
        repayment.account = "Cash - TC"  # This would need to exist in a real test
        
        # Add loan item with valid payment
        repayment.append("loans", {
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member One",
            "loan": "TEST-LOAN-001",
            "loan_type": "Test Personal Loan",
            "outstanding_balance": 10000,
            "payment_amount": 5000,
            "status": "Active"
        })
        
        # This should not throw an error
        repayment.validate()
        
        # Test with payment exceeding balance
        repayment.loans[0].payment_amount = 15000
        with self.assertRaises(frappe.ValidationError):
            repayment.validate()
        
        # Test with zero payment (should be allowed, just ignored)
        repayment.loans[0].payment_amount = 0
        repayment.validate()  # Should not throw error
    
    def test_calculate_totals(self):
        """Test total calculation"""
        repayment = frappe.new_doc("SHG Multi Member Loan Repayment")
        
        # Add multiple loan items
        repayment.append("loans", {
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member One",
            "loan": "TEST-LOAN-001",
            "loan_type": "Test Personal Loan",
            "outstanding_balance": 10000,
            "payment_amount": 3000,
            "status": "Active"
        })
        
        repayment.append("loans", {
            "member": "TEST-MEMBER-002",
            "member_name": "Test Member Two",
            "loan": "TEST-LOAN-002",
            "loan_type": "Test Personal Loan",
            "outstanding_balance": 5000,
            "payment_amount": 2000,
            "status": "Active"
        })
        
        # Add zero payment item (should be ignored)
        repayment.append("loans", {
            "member": "TEST-MEMBER-003",
            "member_name": "Test Member Three",
            "loan": "TEST-LOAN-003",
            "loan_type": "Test Personal Loan",
            "outstanding_balance": 8000,
            "payment_amount": 0,
            "status": "Active"
        })
        
        repayment.calculate_totals()
        
        # Test calculations
        self.assertEqual(repayment.total_payment_amount, 5000)  # 3000 + 2000
        self.assertEqual(repayment.total_selected_loans, 2)     # Only 2 with > 0 payment
    
    def test_payment_method_validation(self):
        """Test payment method validation"""
        repayment = frappe.new_doc("SHG Multi Member Loan Repayment")
        
        # Should throw error without payment method
        with self.assertRaises(frappe.ValidationError):
            repayment.validate()
        
        # Should pass with payment method
        repayment.payment_method = "Cash"
        repayment.company = "Test Company"
        repayment.repayment_date = today()
        repayment.account = "Cash - TC"  # Would need to exist
        repayment.validate()  # Should not throw error
    
    def test_create_multi_member_loan_repayment_api(self):
        """Test the create multi-member loan repayment API"""
        # This test would require proper setup of accounts and company data
        # In a real implementation, you would set up the complete test environment
        pass
    
    def test_loan_repayment_creation(self):
        """Test that individual loan repayments are created"""
        # This would test the process_repayments method
        # Would require mocking or proper test data setup
        pass


def create_test_loan_with_schedule(member_name, loan_amount=10000):
    """Helper function to create a test loan with repayment schedule"""
    # This would create a complete loan with schedule for testing
    pass