import frappe
import unittest
from frappe.utils import flt

class TestInlineRepayment(unittest.TestCase):
    """Test inline repayment functionality."""

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

    def test_pull_unpaid_installments(self):
        """Test that pull_unpaid_installments function works correctly."""
        from shg.shg.api.loan_inline import pull_unpaid_installments
        
        # Pull unpaid installments
        installments = pull_unpaid_installments(self.loan.name)
        
        # Should have 12 unpaid installments
        self.assertEqual(len(installments), 12)
        
        # Check first installment
        first_row = installments[0]
        self.assertIn("name", first_row)
        self.assertIn("installment_no", first_row)
        self.assertIn("due_date", first_row)
        self.assertIn("principal_component", first_row)
        self.assertIn("interest_component", first_row)
        self.assertIn("total_payment", first_row)
        self.assertIn("amount_paid", first_row)
        self.assertIn("unpaid_balance", first_row)
        self.assertIn("status", first_row)
        self.assertIn("remaining_amount", first_row)
        self.assertIn("pay_now", first_row)
        self.assertIn("amount_to_pay", first_row)

    def test_compute_inline_totals(self):
        """Test that compute_inline_totals function calculates correctly."""
        from shg.shg.api.loan_inline import compute_inline_totals
        
        # Compute totals
        totals = compute_inline_totals(self.loan.name)
        
        # For a flat rate loan of 10000 at 12% interest over 12 months:
        # Total interest = 10000 * 0.12 * 1 = 1200
        # Total payable = 11200
        self.assertEqual(flt(totals["outstanding_amount"], 2), flt(11200.00, 2))
        self.assertEqual(flt(totals["overdue_amount"], 2), flt(0.00, 2))  # No overdue yet
        self.assertEqual(flt(totals["total_selected"], 2), flt(0.00, 2))  # No selections yet

    def test_post_inline_repayments(self):
        """Test that post_inline_repayments function works correctly."""
        from shg.shg.api.loan_inline import pull_unpaid_installments, post_inline_repayments
        
        # Pull unpaid installments
        installments = pull_unpaid_installments(self.loan.name)
        
        # Prepare repayment data for first installment
        repayment_data = [{
            "schedule_row_id": installments[0]["name"],
            "amount_to_pay": 500
        }]
        
        # Post repayments
        result = post_inline_repayments(self.loan.name, repayment_data)
        
        # Check result
        self.assertEqual(result["status"], "success")
        self.assertEqual(flt(result["total_paid"], 2), flt(500.00, 2))
        
        # Reload loan document
        self.loan.reload()
        
        # Check that loan fields are updated
        self.assertGreater(flt(self.loan.total_repaid, 2), 0)
        self.assertLess(flt(self.loan.outstanding_balance, 2), flt(11200.00, 2))

    def test_get_installment_remaining_balance(self):
        """Test that get_installment_remaining_balance function works correctly."""
        from shg.shg.api.loan_inline import get_installment_remaining_balance
        
        # Get first schedule row
        schedule_row = self.loan.repayment_schedule[0]
        
        # Calculate remaining balance
        remaining_balance = get_installment_remaining_balance(schedule_row)
        
        # Should equal total_payment - amount_paid
        expected_balance = flt(schedule_row.total_payment) - flt(schedule_row.amount_paid)
        self.assertEqual(flt(remaining_balance, 2), flt(expected_balance, 2))

    def test_compute_aggregate_totals(self):
        """Test that compute_aggregate_totals function calculates correctly."""
        from shg.shg.api.loan_inline import compute_aggregate_totals
        
        # Compute aggregate totals
        totals = compute_aggregate_totals(self.loan.name)
        
        # For a flat rate loan of 10000 at 12% interest over 12 months:
        # Total principal unpaid = 10000
        # Total interest unpaid = 1200
        # Total outstanding = 11200
        self.assertEqual(flt(totals["total_principal_unpaid"], 2), flt(10000.00, 2))
        self.assertEqual(flt(totals["total_interest_unpaid"], 2), flt(1200.00, 2))
        self.assertEqual(flt(totals["total_outstanding"], 2), flt(11200.00, 2))

if __name__ == '__main__':
    unittest.main()