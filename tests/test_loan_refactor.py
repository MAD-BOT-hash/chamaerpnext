import frappe
import unittest
from frappe.utils import flt

class TestLoanRefactor(unittest.TestCase):
    """Test the refactored loan module."""

    def setUp(self):
        """Set up test loan with repayment schedule."""
        # Create a test loan
        self.loan = frappe.new_doc("SHG Loan")
        self.loan.update({
            "member": "_Test Member",
            "loan_type": "Personal Loan",
            "loan_amount": 10000,
            "interest_rate": 12,  # 12% annual interest
            "interest_type": "Flat Rate",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "disbursement_date": "2024-01-01",
            "repayment_start_date": "2024-02-01",
            "status": "Approved"
        })
        self.loan.insert()
        self.loan.submit()
        
        # Create repayment schedule
        self.loan.create_repayment_schedule_if_needed()
        self.loan.save()

    def tearDown(self):
        """Clean up test data."""
        if hasattr(self, 'loan') and self.loan:
            # Cancel and delete repayments first
            repayments = frappe.get_all("SHG Loan Repayment", filters={"loan": self.loan.name})
            for repayment in repayments:
                try:
                    repayment_doc = frappe.get_doc("SHG Loan Repayment", repayment.name)
                    if repayment_doc.docstatus == 1:
                        repayment_doc.cancel()
                    frappe.delete_doc("SHG Loan Repayment", repayment.name)
                except Exception:
                    pass
                    
            # Cancel and delete loan
            try:
                if self.loan.docstatus == 1:
                    self.loan.cancel()
                frappe.delete_doc("SHG Loan", self.loan.name)
            except Exception:
                pass

    def test_field_mappings(self):
        """Test that field mappings are correct."""
        from shg.shg.loan_utils import get_schedule
        
        # Get schedule
        schedule = get_schedule(self.loan.name)
        
        # Check that we're using the correct fields
        first_row = schedule[0]
        self.assertIn("total_payment", first_row)
        self.assertIn("amount_paid", first_row)
        self.assertIn("unpaid_balance", first_row)
        self.assertNotIn("remaining_amount", first_row)

    def test_update_loan_summary_method(self):
        """Test that update_loan_summary method works correctly."""
        # Call the method
        self.loan.update_loan_summary()
        
        # Reload loan document
        self.loan.reload()
        
        # Check that fields are updated
        self.assertGreaterEqual(flt(self.loan.total_payable, 2), 0)
        self.assertGreaterEqual(flt(self.loan.total_repaid, 2), 0)
        self.assertGreaterEqual(flt(self.loan.outstanding_balance, 2), 0)
        self.assertGreaterEqual(flt(self.loan.loan_balance, 2), 0)
        self.assertGreaterEqual(flt(self.loan.balance_amount, 2), 0)
        self.assertGreaterEqual(flt(self.loan.overdue_amount, 2), 0)

    def test_repayment_allocation(self):
        """Test that repayment allocation works correctly."""
        from shg.shg.loan_utils import allocate_payment_to_schedule
        
        # Allocate partial payment
        payment_amount = 1000
        totals = allocate_payment_to_schedule(self.loan.name, payment_amount)
        
        # Check that totals are updated
        self.assertEqual(flt(totals["total_repaid"], 2), flt(payment_amount, 2))
        self.assertEqual(flt(totals["outstanding_balance"], 2), flt(totals["total_payable"] - payment_amount, 2))

    def test_no_remaining_amount_field(self):
        """Test that we're not using remaining_amount field."""
        from shg.shg.loan_utils import get_schedule
        
        # Get schedule
        schedule = get_schedule(self.loan.name)
        
        # Check that we're using unpaid_balance instead of remaining_amount
        first_row = schedule[0]
        self.assertIn("unpaid_balance", first_row)
        self.assertNotIn("remaining_amount", first_row)

    def test_correct_balance_calculation(self):
        """Test that balance calculation includes principal + interest."""
        from shg.shg.loan_utils import get_schedule, compute_totals
        
        # Get schedule
        schedule = get_schedule(self.loan.name)
        
        # Compute totals
        totals = compute_totals(schedule)
        
        # For a flat rate loan of 10000 at 12% interest over 12 months:
        # Total interest = 10000 * 0.12 * 1 = 1200
        # Total payable = 11200
        self.assertEqual(flt(totals["total_payable"], 2), flt(11200.00, 2))
        self.assertEqual(flt(totals["loan_balance"], 2), flt(11200.00, 2))
        self.assertEqual(flt(totals["outstanding_balance"], 2), flt(11200.00, 2))

if __name__ == '__main__':
    unittest.main()