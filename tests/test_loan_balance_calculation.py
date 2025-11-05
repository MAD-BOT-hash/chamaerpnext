import frappe
import unittest
from frappe.utils import flt

class TestLoanBalanceCalculation(unittest.TestCase):
    """Test loan balance calculation functionality."""
    
    def setUp(self):
        """Set up test loan and repayments."""
        # Create a test member
        if not frappe.db.exists("SHG Member", "Test Member - Loan Balance"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "Test Member - Loan Balance",
                "membership_status": "Active"
            })
            member.insert(ignore_permissions=True)
            self.member = member.name
        else:
            self.member = "Test Member - Loan Balance"
        
        # Create a test loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": self.member,
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 12,
            "posting_date": "2025-01-01",
            "application_date": "2025-01-01",
            "disbursement_date": "2025-01-01",
            "repayment_start_date": "2025-02-01",
            "status": "Disbursed"
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
        if frappe.db.exists("SHG Member", self.member):
            frappe.delete_doc("SHG Member", self.member)
    
    def test_loan_balance_with_no_repayments(self):
        """Test loan balance calculation with no repayments."""
        from shg.shg.doctype.shg_loan.shg_loan import get_loan_balance
        
        # Get loan balance
        balance = get_loan_balance(self.loan)
        
        # Should equal the full loan amount
        self.assertEqual(flt(balance, 2), flt(10000, 2))
        
        # Check that the loan document has the correct loan_balance field
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        self.assertEqual(flt(loan_doc.loan_balance, 2), flt(10000, 2))
    
    def test_loan_balance_with_partial_repayments(self):
        """Test loan balance calculation with partial repayments."""
        from shg.shg.doctype.shg_loan.shg_loan import get_loan_balance
        
        # Create a repayment of 3000
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": "2025-02-01",
            "total_paid": 3000
        })
        repayment.insert(ignore_permissions=True)
        repayment.submit()
        
        # Get loan balance
        balance = get_loan_balance(self.loan)
        
        # Should equal the loan amount minus repayments
        self.assertEqual(flt(balance, 2), flt(7000, 2))
        
        # Check that the loan document has the correct loan_balance field
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        self.assertEqual(flt(loan_doc.loan_balance, 2), flt(7000, 2))
    
    def test_loan_balance_with_full_repayment(self):
        """Test loan balance calculation with full repayment."""
        from shg.shg.doctype.shg_loan.shg_loan import get_loan_balance
        
        # Create a repayment of the full loan amount
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": "2025-02-01",
            "total_paid": 10000
        })
        repayment.insert(ignore_permissions=True)
        repayment.submit()
        
        # Get loan balance
        balance = get_loan_balance(self.loan)
        
        # Should equal zero
        self.assertEqual(flt(balance, 2), flt(0, 2))
        
        # Check that the loan document has the correct loan_balance field
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        self.assertEqual(flt(loan_doc.loan_balance, 2), flt(0, 2))
    
    def test_loan_balance_after_repayment_cancellation(self):
        """Test loan balance calculation after repayment cancellation."""
        from shg.shg.doctype.shg_loan.shg_loan import get_loan_balance
        
        # Create a repayment of 3000
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": "2025-02-01",
            "total_paid": 3000
        })
        repayment.insert(ignore_permissions=True)
        repayment.submit()
        
        # Check balance after repayment
        balance = get_loan_balance(self.loan)
        self.assertEqual(flt(balance, 2), flt(7000, 2))
        
        # Cancel the repayment
        repayment.cancel()
        
        # Check balance after cancellation
        balance = get_loan_balance(self.loan)
        self.assertEqual(flt(balance, 2), flt(10000, 2))
        
        # Check that the loan document has the correct loan_balance field
        loan_doc = frappe.get_doc("SHG Loan", self.loan)
        self.assertEqual(flt(loan_doc.loan_balance, 2), flt(10000, 2))

if __name__ == '__main__':
    unittest.main()