import frappe
import unittest
from frappe.utils import flt

class TestLoanBalanceCalculations(unittest.TestCase):
    """Test loan balance calculations with principal and interest components."""

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

    def test_get_outstanding_balance_function(self):
        """Test that get_outstanding_balance function returns correct values."""
        from shg.shg.doctype.shg_loan.shg_loan import get_outstanding_balance
        
        # Get initial balance
        balance_info = get_outstanding_balance(self.loan.name)
        
        # For a flat rate loan of 10000 at 12% interest over 12 months:
        # Total interest = 10000 * 0.12 * 1 = 1200
        # Total payable = 11200
        self.assertEqual(flt(balance_info.get("total_outstanding"), 2), flt(11200.00, 2))
        self.assertEqual(flt(balance_info.get("remaining_principal"), 2), flt(10000.00, 2))
        self.assertEqual(flt(balance_info.get("remaining_interest"), 2), flt(1200.00, 2))

    def test_get_loan_balance_function(self):
        """Test that get_loan_balance function returns correct values."""
        from shg.shg.doctype.shg_loan.shg_loan import get_loan_balance
        
        # Get initial balance
        balance = get_loan_balance(self.loan.name)
        
        # Should be total outstanding (principal + interest)
        self.assertEqual(flt(balance, 2), flt(11200.00, 2))

    def test_partial_repayment_updates_balance(self):
        """Test that partial repayments correctly update loan balance."""
        from shg.shg.doctype.shg_loan.shg_loan import get_outstanding_balance, update_loan_summary
        
        # Create a partial repayment
        repayment = frappe.new_doc("SHG Loan Repayment")
        repayment.update({
            "loan": self.loan.name,
            "posting_date": "2024-02-01",
            "repayment_date": "2024-02-01",
            "total_paid": 1000,
            "principal_amount": 800,
            "interest_amount": 200,
            "mode_of_payment": "Cash"
        })
        repayment.insert()
        repayment.submit()
        
        # Update loan summary
        update_loan_summary(self.loan.name)
        
        # Reload loan document
        self.loan.reload()
        
        # Check that balance is updated correctly
        expected_balance = 11200 - 1000  # 10200
        self.assertEqual(flt(self.loan.balance_amount, 2), flt(expected_balance, 2))
        self.assertEqual(flt(self.loan.loan_balance, 2), flt(expected_balance, 2))
        
        # Check detailed balance
        balance_info = get_outstanding_balance(self.loan.name)
        self.assertEqual(flt(balance_info.get("total_outstanding"), 2), flt(expected_balance, 2))

    def test_repayment_schedule_sync(self):
        """Test that repayment schedule is properly updated with payments."""
        # Create a repayment
        repayment = frappe.new_doc("SHG Loan Repayment")
        repayment.update({
            "loan": self.loan.name,
            "posting_date": "2024-02-01",
            "repayment_date": "2024-02-01",
            "total_paid": 1000,
            "principal_amount": 800,
            "interest_amount": 200,
            "mode_of_payment": "Cash"
        })
        repayment.insert()
        repayment.submit()
        
        # Check that repayment schedule is updated
        schedule_rows = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={"parent": self.loan.name},
            fields=["amount_paid", "unpaid_balance", "status"]
        )
        
        # First installment should be partially paid
        first_row = schedule_rows[0]
        self.assertGreater(flt(first_row.get("amount_paid"), 2), 0)
        self.assertLess(flt(first_row.get("unpaid_balance"), 2), flt(first_row.get("total_payment"), 2))
        self.assertEqual(first_row.get("status"), "Partially Paid")

    def test_update_loan_summary(self):
        """Test that update_loan_summary correctly synchronizes all fields."""
        from shg.shg.doctype.shg_loan.shg_loan import update_loan_summary, get_outstanding_balance
        
        # Create a repayment
        repayment = frappe.new_doc("SHG Loan Repayment")
        repayment.update({
            "loan": self.loan.name,
            "posting_date": "2024-02-01",
            "repayment_date": "2024-02-01",
            "total_paid": 1000,
            "principal_amount": 800,
            "interest_amount": 200,
            "mode_of_payment": "Cash"
        })
        repayment.insert()
        repayment.submit()
        
        # Update loan summary
        result = update_loan_summary(self.loan.name)
        self.assertEqual(result.get("status"), "success")
        
        # Reload loan document
        self.loan.reload()
        
        # Check that all fields are updated
        balance_info = get_outstanding_balance(self.loan.name)
        self.assertEqual(flt(self.loan.balance_amount, 2), flt(balance_info.get("total_outstanding"), 2))
        self.assertEqual(flt(self.loan.loan_balance, 2), flt(balance_info.get("total_outstanding"), 2))
        self.assertEqual(flt(self.loan.total_repaid, 2), flt(1000, 2))

    def test_debug_loan_balance_endpoint(self):
        """Test that debug_loan_balance endpoint returns correct data."""
        from shg.shg.doctype.shg_loan.shg_loan import debug_loan_balance
        
        # Get debug information
        debug_info = debug_loan_balance(self.loan.name)
        
        # Check that all required information is present
        self.assertIn("loan", debug_info)
        self.assertIn("schedule", debug_info)
        self.assertIn("repayments", debug_info)
        self.assertIn("outstanding", debug_info)
        
        # Check loan information
        loan_info = debug_info.get("loan")
        self.assertEqual(loan_info.get("name"), self.loan.name)
        self.assertEqual(loan_info.get("loan_amount"), 10000)
        
        # Check outstanding information
        outstanding_info = debug_info.get("outstanding")
        self.assertIn("remaining_principal", outstanding_info)
        self.assertIn("remaining_interest", outstanding_info)
        self.assertIn("total_outstanding", outstanding_info)

if __name__ == '__main__':
    unittest.main()