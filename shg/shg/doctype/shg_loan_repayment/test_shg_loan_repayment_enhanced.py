import frappe
import unittest
from frappe.utils import nowdate, add_days

class TestSHGLoanRepaymentEnhanced(unittest.TestCase):
    def setUp(self):
        # Create a test loan with repayment schedule
        self.loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "_Test SHG Member",
            "loan_amount": 10000,
            "interest_rate": 12,
            "loan_period_months": 12,
            "repayment_start_date": nowdate()
        })
        self.loan.insert()
        self.loan.submit()
        
        # Create a test repayment
        self.repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan.name,
            "total_paid": 1000,
            "repayment_date": nowdate(),
            "posting_date": nowdate()
        })
        
    def tearDown(self):
        # Clean up test data
        if frappe.db.exists("SHG Loan Repayment", self.repayment.name):
            frappe.delete_doc("SHG Loan Repayment", self.repayment.name)
        frappe.delete_doc("SHG Loan", self.loan.name)
        
    def test_repayment_validation(self):
        """Test that repayment validation works correctly."""
        # Test that repayment amount must be greater than zero
        self.repayment.total_paid = 0
        with self.assertRaises(frappe.ValidationError) as context:
            self.repayment.save()
        self.assertIn("Repayment amount must be greater than zero", str(context.exception))
        
        # Test that repayment cannot exceed outstanding balance
        self.repayment.total_paid = 15000  # Exceeds loan amount
        with self.assertRaises(frappe.ValidationError) as context:
            self.repayment.save()
        self.assertIn("exceeds remaining balance", str(context.exception))
        
    def test_repayment_breakdown_calculation(self):
        """Test that repayment breakdown is calculated correctly."""
        # Set a valid repayment amount
        self.repayment.total_paid = 1000
        self.repayment.save()
        
        # Call the breakdown calculation method
        result = self.repayment.calculate_repayment_breakdown()
        
        # Verify that all breakdown fields are populated
        self.assertIsNotNone(self.repayment.principal_amount)
        self.assertIsNotNone(self.repayment.interest_amount)
        self.assertIsNotNone(self.repayment.penalty_amount)
        self.assertIsNotNone(self.repayment.outstanding_balance)
        self.assertIsNotNone(self.repayment.balance_after_payment)
        
    def test_on_submit_updates_schedule(self):
        """Test that on_submit updates the repayment schedule correctly."""
        # Set a valid repayment amount
        self.repayment.total_paid = 1000
        self.repayment.insert()
        self.repayment.submit()
        
        # Reload the loan to check updated values
        self.loan.reload()
        
        # Verify that loan summary fields are updated
        self.assertGreater(self.loan.total_repaid, 0)
        self.assertLess(self.loan.balance_amount, self.loan.loan_amount)
        
    def test_on_cancel_reverses_schedule(self):
        """Test that on_cancel reverses the repayment schedule updates."""
        # First submit a repayment
        self.repayment.total_paid = 1000
        self.repayment.insert()
        self.repayment.submit()
        
        # Get the loan balance after repayment
        self.loan.reload()
        balance_after_repayment = self.loan.balance_amount
        
        # Cancel the repayment
        self.repayment.cancel()
        
        # Reload the loan to check reversed values
        self.loan.reload()
        
        # Verify that loan summary fields are reversed
        self.assertEqual(self.loan.total_repaid, 0)
        self.assertEqual(self.loan.balance_amount, self.loan.loan_amount)
        
    def test_get_unpaid_schedule_rows(self):
        """Test that get_unpaid_schedule_rows returns correct data."""
        from shg.shg.doctype.shg_loan_repayment.shg_loan_repayment import get_unpaid_schedule_rows
        
        # Get unpaid schedule rows for the test loan
        result = get_unpaid_schedule_rows(self.loan.name)
        
        # Verify that result is a list
        self.assertIsInstance(result, list)
        
        # Verify that each item has the required fields
        if result:
            for item in result:
                self.assertIn("value", item)
                self.assertIn("label", item)