import frappe
import unittest
from frappe.utils import today, add_months


class TestRepaymentBalanceCalculation(unittest.TestCase):
    """Test cases for repayment balance calculation fixes."""

    def setUp(self):
        """Set up test loan and repayment data."""
        # Create a test member
        if not frappe.db.exists("SHG Member", "_Test Member RBC"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member RBC",
                "date_of_birth": "1990-01-01",
                "gender": "Male",
                "mobile_number": "1234567890",
                "email": "test_rbc@example.com",
                "address": "Test Address",
                "joining_date": "2024-01-01",
                "membership_status": "Active"
            })
            member.insert(ignore_permissions=True)
            self.member = member.name
        else:
            self.member = "_Test Member RBC"

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
            "repayment_start_date": today(),
            "company": frappe.db.get_single_value("SHG Settings", "company") or "_Test Company"
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

        # Delete test member
        if frappe.db.exists("SHG Member", "_Test Member RBC"):
            frappe.delete_doc("SHG Member", "_Test Member RBC")

    def test_get_remaining_balance_function(self):
        """Test that get_remaining_balance function returns correct values."""
        from shg.shg.doctype.shg_loan.shg_loan import get_remaining_balance
        
        # Get initial balance
        balance_info = get_remaining_balance(self.loan)
        
        # For a flat rate loan of 10000 at 12% interest over 12 months:
        # Total interest = 10000 * 0.12 * 1 = 1200
        # Total payable = 11200
        self.assertEqual(flt(balance_info["total_balance"], 2), flt(11200.00, 2))
        self.assertEqual(flt(balance_info["principal_balance"], 2), flt(10000.00, 2))
        self.assertEqual(flt(balance_info["interest_balance"], 2), flt(1200.00, 2))

    def test_repayment_validation_with_correct_balance(self):
        """Test that repayment validation uses correct balance calculation."""
        # Get the loan document
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        
        # Check initial balance
        initial_balance = loan_doc.balance_amount
        self.assertEqual(flt(initial_balance, 2), flt(11200.00, 2))
        
        # Create a repayment for 1000 (should be accepted)
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": today(),
            "total_paid": 1000
        })
        repayment.insert(ignore_permissions=True)
        repayment.submit()
        
        # Check that the repayment was successful
        self.assertEqual(repayment.docstatus, 1)
        
        # Reload loan to check updated balance
        loan_doc.reload()
        
        # Create another repayment to test validation
        repayment2 = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": today(),
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
                "posting_date": today(),
                "total_paid": 20000  # This should exceed the balance
            })
            repayment.insert(ignore_permissions=True)
            repayment.submit()
        
        # Check that the error message is correct
        self.assertIn("exceeds remaining balance", str(context.exception))

    def test_repayment_schedule_updates_after_payment(self):
        """Test that repayment schedule is properly updated after payment."""
        # Create a repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": today(),
            "total_paid": 1000
        })
        repayment.insert(ignore_permissions=True)
        repayment.submit()
        
        # Reload loan to get updated schedule
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        loan_doc.reload()
        
        # Check that schedule rows have been updated
        total_paid = sum(flt(row.amount_paid) for row in loan_doc.repayment_schedule)
        total_unpaid = sum(flt(row.unpaid_balance) for row in loan_doc.repayment_schedule)
        
        self.assertEqual(flt(total_paid, 2), flt(1000.00, 2))
        self.assertEqual(flt(total_unpaid, 2), flt(10200.00, 2))  # 11200 - 1000

    def test_loan_summary_synchronization(self):
        """Test that loan summary fields are synchronized with schedule."""
        # Create a repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": today(),
            "total_paid": 1000
        })
        repayment.insert(ignore_permissions=True)
        repayment.submit()
        
        # Reload loan to check updated fields
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        loan_doc.reload()
        
        # Check that summary fields are updated
        self.assertEqual(flt(loan_doc.total_repaid, 2), flt(1000.00, 2))
        self.assertEqual(flt(loan_doc.balance_amount, 2), flt(10200.00, 2))  # 11200 - 1000