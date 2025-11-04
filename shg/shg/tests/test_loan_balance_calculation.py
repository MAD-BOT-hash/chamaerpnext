import frappe
import unittest
from frappe.utils import today, add_months

class TestLoanBalanceCalculation(unittest.TestCase):
    """Test cases for SHG Loan balance calculation."""
    
    def setUp(self):
        """Set up test data before each test."""
        # Create a test member
        if not frappe.db.exists("SHG Member", "_Test Member"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member",
                "membership_status": "Active"
            })
            member.insert(ignore_permissions=True)
    
    def tearDown(self):
        """Clean up test data after each test."""
        # Clean up created documents
        frappe.db.sql("DELETE FROM `tabSHG Loan Repayment` WHERE loan IN (SELECT name FROM `tabSHG Loan` WHERE member = '_Test Member')")
        frappe.db.sql("DELETE FROM `tabSHG Loan` WHERE member = '_Test Member'")
        frappe.db.sql("DELETE FROM `tabSHG Member` WHERE member_name = '_Test Member'")
        frappe.db.commit()
    
    def test_loan_with_no_repayments(self):
        """Test loan balance calculation with no repayments."""
        # Create a loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "_Test Member",
            "member_name": "_Test Member",
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "application_date": today(),
            "posting_date": today(),
            "repayment_start_date": add_months(today(), 1),
            "status": "Approved"
        })
        loan.insert(ignore_permissions=True)
        loan.submit()
        
        # Check that loan balance equals loan amount
        self.assertEqual(loan.loan_balance, 10000)
        self.assertEqual(loan.loan_amount, 10000)
    
    def test_loan_with_partial_repayments(self):
        """Test loan balance calculation with partial repayments."""
        # Create a loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "_Test Member",
            "member_name": "_Test Member",
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "application_date": today(),
            "posting_date": today(),
            "repayment_start_date": add_months(today(), 1),
            "status": "Approved"
        })
        loan.insert(ignore_permissions=True)
        loan.submit()
        
        # Create a partial repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": "_Test Member",
            "posting_date": today(),
            "total_paid": 3000,
            "principal_amount": 3000,
            "interest_amount": 0,
            "penalty_amount": 0
        })
        repayment.insert(ignore_permissions=True)
        repayment.submit()
        
        # Reload loan to get updated values
        loan.reload()
        
        # Check that loan balance is reduced by principal repayment
        self.assertEqual(loan.loan_balance, 7000)  # 10000 - 3000
        self.assertEqual(loan.loan_amount, 10000)
    
    def test_loan_fully_repaid(self):
        """Test loan balance calculation when fully repaid."""
        # Create a loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "_Test Member",
            "member_name": "_Test Member",
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "application_date": today(),
            "posting_date": today(),
            "repayment_start_date": add_months(today(), 1),
            "status": "Approved"
        })
        loan.insert(ignore_permissions=True)
        loan.submit()
        
        # Create a full repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": "_Test Member",
            "posting_date": today(),
            "total_paid": 10000,
            "principal_amount": 10000,
            "interest_amount": 0,
            "penalty_amount": 0
        })
        repayment.insert(ignore_permissions=True)
        repayment.submit()
        
        # Reload loan to get updated values
        loan.reload()
        
        # Check that loan balance is zero
        self.assertEqual(loan.loan_balance, 0)
        self.assertEqual(loan.loan_amount, 10000)
    
    def test_repayment_cancellation(self):
        """Test that loan balance is recalculated when repayment is cancelled."""
        # Create a loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "_Test Member",
            "member_name": "_Test Member",
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "application_date": today(),
            "posting_date": today(),
            "repayment_start_date": add_months(today(), 1),
            "status": "Approved"
        })
        loan.insert(ignore_permissions=True)
        loan.submit()
        
        # Create a repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": "_Test Member",
            "posting_date": today(),
            "total_paid": 5000,
            "principal_amount": 5000,
            "interest_amount": 0,
            "penalty_amount": 0
        })
        repayment.insert(ignore_permissions=True)
        repayment.submit()
        
        # Reload loan to get updated values
        loan.reload()
        
        # Check that loan balance is reduced
        self.assertEqual(loan.loan_balance, 5000)  # 10000 - 5000
        
        # Cancel the repayment
        repayment.cancel()
        
        # Reload loan to get updated values
        loan.reload()
        
        # Check that loan balance is restored
        self.assertEqual(loan.loan_balance, 10000)  # Back to original amount

# Run tests if executed directly
if __name__ == '__main__':
    unittest.main()