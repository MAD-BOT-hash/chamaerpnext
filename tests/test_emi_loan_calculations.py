import frappe
import unittest
from frappe.utils import flt

class TestEMILoanCalculations(unittest.TestCase):
    """Test EMI-based loan calculations."""

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

    def test_get_schedule_function(self):
        """Test that get_schedule function returns correct data."""
        from shg.shg.loan_utils import get_schedule
        
        # Get schedule
        schedule = get_schedule(self.loan.name)
        
        # Should have 12 installments
        self.assertEqual(len(schedule), 12)
        
        # Check first installment
        first_row = schedule[0]
        self.assertIn("name", first_row)
        self.assertIn("due_date", first_row)
        self.assertIn("principal_component", first_row)
        self.assertIn("interest_component", first_row)
        self.assertIn("total_payment", first_row)
        self.assertIn("amount_paid", first_row)
        self.assertIn("remaining_amount", first_row)
        self.assertIn("status", first_row)

    def test_compute_totals_function(self):
        """Test that compute_totals function calculates correctly."""
        from shg.shg.loan_utils import get_schedule, compute_totals
        
        # Get schedule
        schedule = get_schedule(self.loan.name)
        
        # Compute totals
        totals = compute_totals(schedule)
        
        # For a flat rate loan of 10000 at 12% interest over 12 months:
        # Total interest = 10000 * 0.12 * 1 = 1200
        # Total payable = 11200
        self.assertEqual(flt(totals["total_payable"], 2), flt(11200.00, 2))
        self.assertEqual(flt(totals["total_principal"], 2), flt(10000.00, 2))
        self.assertEqual(flt(totals["total_interest"], 2), flt(1200.00, 2))
        self.assertEqual(flt(totals["loan_balance"], 2), flt(11200.00, 2))
        self.assertEqual(flt(totals["total_repaid"], 2), flt(0.00, 2))

    def test_update_loan_summary_function(self):
        """Test that update_loan_summary function updates loan fields."""
        from shg.shg.loan_utils import update_loan_summary
        
        # Update loan summary
        totals = update_loan_summary(self.loan.name)
        
        # Reload loan document
        self.loan.reload()
        
        # Check that loan fields are updated
        self.assertEqual(flt(self.loan.total_payable, 2), flt(11200.00, 2))
        self.assertEqual(flt(self.loan.loan_balance, 2), flt(11200.00, 2))
        self.assertEqual(flt(self.loan.balance_amount, 2), flt(11200.00, 2))
        self.assertEqual(flt(self.loan.total_repaid, 2), flt(0.00, 2))

    def test_allocate_payment_to_schedule_function(self):
        """Test that allocate_payment_to_schedule function works correctly."""
        from shg.shg.loan_utils import allocate_payment_to_schedule, get_schedule
        
        # Allocate partial payment
        payment_amount = 1000
        totals = allocate_payment_to_schedule(self.loan.name, payment_amount)
        
        # Check that totals are updated
        self.assertEqual(flt(totals["total_repaid"], 2), flt(payment_amount, 2))
        self.assertEqual(flt(totals["loan_balance"], 2), flt(11200.00 - payment_amount, 2))
        
        # Check schedule rows
        schedule = get_schedule(self.loan.name)
        first_row = schedule[0]
        self.assertGreater(flt(first_row.amount_paid, 2), 0)
        self.assertEqual(first_row.status, "Partially Paid")

    def test_get_unpaid_installments_api(self):
        """Test that get_unpaid_installments API returns correct data."""
        from shg.shg.api.loan import get_unpaid_installments
        
        # Get unpaid installments
        unpaid = get_unpaid_installments(self.loan.name)
        
        # Should have 12 unpaid installments
        self.assertEqual(len(unpaid), 12)
        
        # Make a partial payment
        from shg.shg.loan_utils import allocate_payment_to_schedule
        allocate_payment_to_schedule(self.loan.name, 1000)
        
        # Get unpaid installments again
        unpaid = get_unpaid_installments(self.loan.name)
        
        # Should still have 12 rows (one partially paid)
        self.assertEqual(len(unpaid), 12)

    def test_post_repayment_allocation_api(self):
        """Test that post_repayment_allocation API works correctly."""
        from shg.shg.api.loan import post_repayment_allocation
        
        # Post repayment allocation
        result = post_repayment_allocation(self.loan.name, 1000)
        
        # Check result
        self.assertEqual(result["message"], "Repayment allocated")
        self.assertIn("totals", result)
        self.assertEqual(flt(result["totals"]["total_repaid"], 2), flt(1000, 2))

if __name__ == '__main__':
    unittest.main()