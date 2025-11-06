import frappe
import unittest
from frappe.utils import flt


class TestLoanRepaymentBalanceFix(unittest.TestCase):
    """Test cases for the loan repayment balance calculation fix."""

    def setUp(self):
        """Set up test loan and repayment data."""
        # Create a test member
        if not frappe.db.exists("SHG Member", "_Test Member LR"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member LR",
                "date_of_birth": "1990-01-01",
                "gender": "Male",
                "mobile_number": "1234567890",
                "email": "test_lr@example.com",
                "address": "Test Address",
                "joining_date": "2024-01-01",
                "membership_status": "Active"
            })
            member.insert(ignore_permissions=True)
            self.member = member.name
        else:
            self.member = "_Test Member LR"

        # Create a test loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": self.member,
            "loan_type": "Individual Loan",
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "repayment_start_date": "2025-01-01",
            "company": frappe.db.get_single_value("SHG Settings", "company") or "Test Company"
        })
        loan.insert(ignore_permissions=True)
        loan.submit()
        self.loan = loan.name

    def tearDown(self):
        """Clean up test data."""
        # Cancel and delete test repayments
        repayments = frappe.get_all("SHG Loan Repayment", filters={"loan": self.loan})
        for repayment in repayments:
            repayment_doc = frappe.get_doc("SHG Loan Repayment", repayment.name)
            if repayment_doc.docstatus == 1:
                repayment_doc.cancel()
            frappe.delete_doc("SHG Loan Repayment", repayment.name)

        # Cancel and delete test loan
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        if loan_doc.docstatus == 1:
            loan_doc.cancel()
        frappe.delete_doc("SHG Loan", self.loan)

        # Delete test member if it was created for this test
        if frappe.db.exists("SHG Member", "_Test Member LR"):
            frappe.delete_doc("SHG Member", "_Test Member LR")

    def test_repayment_validation_with_dynamic_balance_calculation(self):
        """Test that repayment validation uses dynamic balance calculation."""
        # Get the loan document
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        
        # Check initial balance
        initial_balance = loan_doc.balance_amount
        self.assertEqual(flt(initial_balance, 2), flt(11200.00, 2))  # 10000 + 1200 interest
        
        # Create a repayment for 1000
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": "2025-01-15",
            "total_paid": 1000
        })
        repayment.insert(ignore_permissions=True)
        repayment.submit()
        
        # Check that the repayment was successful
        self.assertEqual(repayment.docstatus, 1)
        
        # Create another repayment to test validation
        repayment2 = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": "2025-01-20",
            "total_paid": 1000
        })
        repayment2.insert(ignore_permissions=True)
        repayment2.submit()
        
        # Check that the second repayment was successful
        self.assertEqual(repayment2.docstatus, 1)
        
    def test_repayment_exceeds_balance_validation(self):
        """Test that repayment validation correctly rejects amounts exceeding balance."""
        # Try to create a repayment that exceeds the balance
        with self.assertRaises(frappe.ValidationError) as context:
            repayment = frappe.get_doc({
                "doctype": "SHG Loan Repayment",
                "loan": self.loan,
                "posting_date": "2025-01-15",
                "total_paid": 20000  # This should exceed the balance
            })
            repayment.insert(ignore_permissions=True)
            repayment.submit()
        
        # Check that the error message is correct
        self.assertIn("exceeds remaining balance", str(context.exception))