import frappe
import unittest
from frappe.utils import flt

class TestInlineRepaymentWorkflow(unittest.TestCase):
    """Test inline repayment workflow."""

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
        """Test pulling unpaid installments."""
        from shg.shg.api.repayment_utils import pull_unpaid_installments
        
        # Pull unpaid installments
        installments = pull_unpaid_installments(self.loan.name)
        
        # Should have 12 unpaid installments
        self.assertEqual(len(installments), 12)
        
        # Check first installment has required fields
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

    def test_post_inline_repayments(self):
        """Test posting inline repayments."""
        from shg.shg.api.repayment_utils import pull_unpaid_installments, post_inline_repayments
        
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

    def test_partial_payment_updates(self):
        """Test that partial payments update schedule rows correctly."""
        from shg.shg.api.repayment_utils import pull_unpaid_installments, post_inline_repayments
        
        # Pull unpaid installments
        installments = pull_unpaid_installments(self.loan.name)
        
        # Get first installment details
        first_installment = installments[0]
        total_payment = flt(first_installment["total_payment"])
        amount_to_pay = 500
        
        # Prepare repayment data
        repayment_data = [{
            "schedule_row_id": first_installment["name"],
            "amount_to_pay": amount_to_pay
        }]
        
        # Post repayments
        post_inline_repayments(self.loan.name, repayment_data)
        
        # Check that schedule row is updated correctly
        schedule_row = frappe.get_doc("SHG Loan Repayment Schedule", first_installment["name"])
        
        # Amount paid should be updated
        self.assertEqual(flt(schedule_row.amount_paid, 2), flt(amount_to_pay, 2))
        
        # Unpaid balance should be reduced
        expected_unpaid = total_payment - amount_to_pay
        self.assertEqual(flt(schedule_row.unpaid_balance, 2), flt(expected_unpaid, 2))
        
        # Status should be Partially Paid
        self.assertEqual(schedule_row.status, "Partially Paid")

    def test_full_payment_closes_installment(self):
        """Test that full payments close installments."""
        from shg.shg.api.repayment_utils import pull_unpaid_installments, post_inline_repayments
        
        # Pull unpaid installments
        installments = pull_unpaid_installments(self.loan.name)
        
        # Get first installment details
        first_installment = installments[0]
        total_payment = flt(first_installment["total_payment"])
        
        # Prepare repayment data for full payment
        repayment_data = [{
            "schedule_row_id": first_installment["name"],
            "amount_to_pay": total_payment
        }]
        
        # Post repayments
        post_inline_repayments(self.loan.name, repayment_data)
        
        # Check that schedule row is updated correctly
        schedule_row = frappe.get_doc("SHG Loan Repayment Schedule", first_installment["name"])
        
        # Amount paid should equal total payment
        self.assertEqual(flt(schedule_row.amount_paid, 2), flt(total_payment, 2))
        
        # Unpaid balance should be zero
        self.assertEqual(flt(schedule_row.unpaid_balance, 2), 0)
        
        # Status should be Paid
        self.assertEqual(schedule_row.status, "Paid")
        
        # Actual payment date should be set
        self.assertIsNotNone(schedule_row.actual_payment_date)

    def test_repayment_validation(self):
        """Test repayment validation."""
        from shg.shg.api.repayment_utils import pull_unpaid_installments, post_inline_repayments
        
        # Pull unpaid installments
        installments = pull_unpaid_installments(self.loan.name)
        
        # Get first installment details
        first_installment = installments[0]
        unpaid_balance = flt(first_installment["unpaid_balance"])
        
        # Prepare repayment data with excessive amount
        repayment_data = [{
            "schedule_row_id": first_installment["name"],
            "amount_to_pay": unpaid_balance + 1000  # Exceeds unpaid balance
        }]
        
        # Attempt to post repayments - should fail
        with self.assertRaises(Exception):
            post_inline_repayments(self.loan.name, repayment_data)

if __name__ == '__main__':
    unittest.main()