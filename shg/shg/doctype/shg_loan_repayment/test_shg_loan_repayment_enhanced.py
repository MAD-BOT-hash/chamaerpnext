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
        
    def test_fetch_unpaid_installments(self):
        """Test that fetch_unpaid_installments populates the child table correctly."""
        # Call the method
        self.repayment.fetch_unpaid_installments()
        
        # Verify that installment adjustments were populated
        self.assertTrue(len(self.repayment.installment_adjustment) > 0)
        
        # Verify that the first row has correct data
        first_row = self.repayment.installment_adjustment[0]
        self.assertIsNotNone(first_row.installment_no)
        self.assertIsNotNone(first_row.due_date)
        self.assertIsNotNone(first_row.emi_amount)
        self.assertIsNotNone(first_row.principal_amount)
        self.assertIsNotNone(first_row.interest_amount)
        self.assertIsNotNone(first_row.unpaid_balance)
        self.assertIsNotNone(first_row.status)
        
    def test_amount_to_repay_validation(self):
        """Test that amount to repay validation works correctly."""
        # Fetch unpaid installments first
        self.repayment.fetch_unpaid_installments()
        
        # Try to set amount to repay higher than unpaid balance
        if self.repayment.installment_adjustment:
            first_row = self.repayment.installment_adjustment[0]
            first_row.amount_to_repay = first_row.unpaid_balance + 1000  # Exceed unpaid balance
            
            # This should raise a validation error
            with self.assertRaises(frappe.ValidationError):
                self.repayment.save()
                
    def test_remaining_amount_calculation(self):
        """Test that remaining amount is calculated correctly."""
        # Fetch unpaid installments first
        self.repayment.fetch_unpaid_installments()
        
        if self.repayment.installment_adjustment:
            first_row = self.repayment.installment_adjustment[0]
            original_unpaid = first_row.unpaid_balance
            amount_to_repay = original_unpaid / 2
            first_row.amount_to_repay = amount_to_repay
            
            # Calculate expected remaining amount
            expected_remaining = original_unpaid - amount_to_repay
            
            # Verify remaining amount calculation
            self.assertEqual(first_row.remaining_amount, expected_remaining)
            
    def test_status_update(self):
        """Test that status is updated correctly based on amount to repay."""
        # Fetch unpaid installments first
        self.repayment.fetch_unpaid_installments()
        
        if self.repayment.installment_adjustment:
            first_row = self.repayment.installment_adjustment[0]
            original_unpaid = first_row.unpaid_balance
            
            # Test Partially Paid status
            first_row.amount_to_repay = original_unpaid / 2
            self.assertEqual(first_row.status, "Partially Paid")
            
            # Test Paid status
            first_row.amount_to_repay = original_unpaid
            self.assertEqual(first_row.status, "Paid")
            
            # Test Unpaid status
            first_row.amount_to_repay = 0
            self.assertEqual(first_row.status, "Unpaid")