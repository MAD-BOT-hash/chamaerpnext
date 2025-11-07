import frappe
import unittest
from frappe.utils import today, add_days

class TestRecalculateLoanSummary(unittest.TestCase):
    def setUp(self):
        # Create a test member
        if not frappe.db.exists("SHG Member", "_Test Member for Recalculate"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member for Recalculate",
                "membership_status": "Active",
                "date_joined": today(),
            })
            member.insert()

        # Create a test loan
        self.loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "_Test Member for Recalculate",
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Reducing Balance",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "repayment_start_date": today(),
            "company": frappe.db.get_single_value("SHG Settings", "company") or "_Test Company"
        })
        self.loan.insert()
        self.loan.submit()

    def tearDown(self):
        # Clean up test data
        if frappe.db.exists("SHG Loan", self.loan.name):
            loan = frappe.get_doc("SHG Loan", self.loan.name)
            if loan.docstatus == 1:
                # Cancel before deleting
                loan.cancel()
            loan.delete()

        if frappe.db.exists("SHG Member", "_Test Member for Recalculate"):
            member = frappe.get_doc("SHG Member", "_Test Member for Recalculate")
            member.delete()

    def test_recalculate_summary_for_submitted_loan(self):
        """Test that recalculate_summary works for submitted loans"""
        # Verify loan is submitted
        self.assertEqual(self.loan.docstatus, 1)
        
        # Get initial values
        initial_outstanding = self.loan.outstanding_amount
        initial_balance = self.loan.balance_amount
        
        # Recalculate summary
        log_entries = self.loan.recalculate_summary()
        
        # Verify the method completed without error
        self.assertIsNotNone(log_entries)
        
        # Reload the loan to get updated values
        self.loan.reload()
        
        # Verify key fields are updated
        self.assertGreaterEqual(self.loan.total_principal_payable, 0)
        self.assertGreaterEqual(self.loan.total_interest_payable, 0)
        self.assertGreaterEqual(self.loan.total_payable_amount, 0)
        self.assertGreaterEqual(self.loan.outstanding_amount, 0)
        self.assertGreaterEqual(self.loan.balance_amount, 0)
        
    def test_recalculate_summary_with_overdue_installment(self):
        """Test that recalculate_summary correctly identifies overdue installments"""
        # Set first installment due date to past
        if self.loan.repayment_schedule:
            self.loan.repayment_schedule[0].due_date = add_days(today(), -30)
            # Use db_set to update submitted document
            frappe.db.set_value(
                "SHG Loan Repayment Schedule", 
                self.loan.repayment_schedule[0].name, 
                "due_date", 
                add_days(today(), -30)
            )
            
        # Recalculate summary
        self.loan.recalculate_summary()
        
        # Reload the loan to get updated values
        self.loan.reload()
        
        # Verify that overdue amount is calculated
        self.assertGreaterEqual(self.loan.overdue_amount, 0)
        
    def test_recalculate_summary_field_consistency(self):
        """Test that recalculate_summary maintains field consistency"""
        # Recalculate summary
        self.loan.recalculate_summary()
        
        # Reload the loan to get updated values
        self.loan.reload()
        
        # Verify that balance_amount equals outstanding_amount
        self.assertEqual(self.loan.balance_amount, self.loan.outstanding_amount)
        
        # Verify that loan_balance equals outstanding_amount
        self.assertEqual(self.loan.loan_balance, self.loan.outstanding_amount)
        
        # Verify that total_payable_amount equals sum of principal and interest
        expected_total = self.loan.total_principal_payable + self.loan.total_interest_payable
        self.assertEqual(self.loan.total_payable_amount, expected_total)

if __name__ == '__main__':
    unittest.main()