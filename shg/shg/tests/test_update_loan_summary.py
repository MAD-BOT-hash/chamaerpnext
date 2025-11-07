import frappe
import unittest
from frappe.utils import today, add_days

class TestUpdateLoanSummary(unittest.TestCase):
    def setUp(self):
        # Create a test member
        if not frappe.db.exists("SHG Member", "_Test Member for Loan Summary"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member for Loan Summary",
                "membership_status": "Active",
                "date_joined": today(),
            })
            member.insert()

        # Create a test loan
        self.loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "_Test Member for Loan Summary",
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
                loan.cancel()
            loan.delete()

        if frappe.db.exists("SHG Member", "_Test Member for Loan Summary"):
            member = frappe.get_doc("SHG Member", "_Test Member for Loan Summary")
            member.delete()

    def test_update_loan_summary_function(self):
        """Test that update_loan_summary function works correctly"""
        from shg.shg.loan_utils import update_loan_summary
        
        # Call the function
        result = update_loan_summary(self.loan.name)
        
        # Verify that the function completed successfully
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "success")
        
        # Reload the loan to get updated values
        self.loan.reload()
        
        # Verify that key fields are populated
        self.assertIsNotNone(self.loan.total_principal_payable)
        self.assertIsNotNone(self.loan.total_interest_payable)
        self.assertIsNotNone(self.loan.total_payable_amount)
        self.assertIsNotNone(self.loan.total_amount_paid)
        self.assertIsNotNone(self.loan.outstanding_amount)
        self.assertIsNotNone(self.loan.balance_amount)
        self.assertIsNotNone(self.loan.loan_balance)
        self.assertIsNotNone(self.loan.overdue_amount)
        self.assertIsNotNone(self.loan.percent_repaid)
        
        # Verify that balance_amount equals loan_balance and outstanding_amount
        self.assertEqual(self.loan.balance_amount, self.loan.loan_balance)
        self.assertEqual(self.loan.balance_amount, self.loan.outstanding_amount)

    def test_overdue_calculation(self):
        """Test that overdue amount is calculated correctly"""
        from shg.shg.loan_utils import update_loan_summary
        
        # Set first installment due date to past to make it overdue
        if self.loan.repayment_schedule:
            self.loan.repayment_schedule[0].due_date = add_days(today(), -30)
            # Use db_set to update submitted document
            frappe.db.set_value(
                "SHG Loan Repayment Schedule", 
                self.loan.repayment_schedule[0].name, 
                "due_date", 
                add_days(today(), -30)
            )
            
        # Update loan summary
        update_loan_summary(self.loan.name)
        
        # Reload the loan to get updated values
        self.loan.reload()
        
        # Verify that overdue amount is calculated
        self.assertGreaterEqual(self.loan.overdue_amount, 0)

    def test_next_due_date_calculation(self):
        """Test that next due date is calculated correctly"""
        from shg.shg.loan_utils import update_loan_summary
        
        # Update loan summary
        update_loan_summary(self.loan.name)
        
        # Reload the loan to get updated values
        self.loan.reload()
        
        # Verify that next due date is set
        self.assertIsNotNone(self.loan.next_due_date)

    def test_percent_repaid_calculation(self):
        """Test that percent repaid is calculated correctly"""
        from shg.shg.loan_utils import update_loan_summary
        
        # Update loan summary
        update_loan_summary(self.loan.name)
        
        # Reload the loan to get updated values
        self.loan.reload()
        
        # Verify that percent repaid is calculated
        self.assertIsNotNone(self.loan.percent_repaid)
        self.assertGreaterEqual(self.loan.percent_repaid, 0)
        self.assertLessEqual(self.loan.percent_repaid, 100)

if __name__ == '__main__':
    unittest.main()