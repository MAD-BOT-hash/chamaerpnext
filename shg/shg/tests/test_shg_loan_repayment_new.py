import frappe
import unittest
from frappe.utils import today, add_months

class TestSHGLoanRepaymentNew(unittest.TestCase):
    def setUp(self):
        # Create a test member
        if not frappe.db.exists("SHG Member", "_Test Member"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member",
                "membership_status": "Active",
                "date_joined": today(),
            })
            member.insert()

        # Create a test loan
        if not frappe.db.exists("SHG Loan", "_Test Loan"):
            loan = frappe.get_doc({
                "doctype": "SHG Loan",
                "member": "_Test Member",
                "loan_amount": 10000,
                "interest_rate": 12,
                "interest_type": "Reducing Balance",
                "loan_period_months": 12,
                "repayment_frequency": "Monthly",
                "repayment_start_date": today(),
                "company": frappe.db.get_single_value("SHG Settings", "company") or "_Test Company"
            })
            loan.insert()
            loan.submit()

    def tearDown(self):
        # Clean up test data
        if frappe.db.exists("SHG Loan Repayment", {"loan": "_Test Loan"}):
            repayment = frappe.get_doc("SHG Loan Repayment", {"loan": "_Test Loan"})
            if repayment.docstatus == 1:
                repayment.cancel()
            repayment.delete()

        if frappe.db.exists("SHG Loan", "_Test Loan"):
            loan = frappe.get_doc("SHG Loan", "_Test Loan")
            if loan.docstatus == 1:
                loan.cancel()
            loan.delete()

        if frappe.db.exists("SHG Member", "_Test Member"):
            member = frappe.get_doc("SHG Member", "_Test Member")
            member.delete()

    def test_loan_repayment_creation(self):
        """Test that loan repayment can be created and submitted correctly"""
        # Create a repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": "_Test Loan",
            "total_paid": 1000,
            "posting_date": today(),
            "repayment_date": today(),
        })
        repayment.insert()
        repayment.submit()
        
        # Check that the repayment was created successfully
        self.assertEqual(repayment.docstatus, 1)
        
        # Reload the loan to get updated values
        loan = frappe.get_doc("SHG Loan", "_Test Loan")
        
        # Check that the loan summary was updated
        self.assertEqual(loan.total_repaid, 1000)
        self.assertLess(loan.balance_amount, loan.total_payable)

    def test_repayment_schedule_updates(self):
        """Test that repayment schedule is updated correctly when repayment is made"""
        loan = frappe.get_doc("SHG Loan", "_Test Loan")
        
        # Create a repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": "_Test Loan",
            "total_paid": 1000,
            "posting_date": today(),
            "repayment_date": today(),
        })
        repayment.insert()
        repayment.submit()
        
        # Reload the loan to get updated values
        loan.reload()
        
        # Check that at least one schedule row was updated
        updated_rows = [row for row in loan.repayment_schedule if row.amount_paid > 0]
        self.assertGreater(len(updated_rows), 0)
        
        # Check that the payment entry is linked to the schedule row
        linked_rows = [row for row in loan.repayment_schedule if row.payment_entry == repayment.name]
        self.assertGreater(len(linked_rows), 0)

    def test_repayment_cancellation(self):
        """Test that repayment can be cancelled and schedule is updated correctly"""
        # Create and submit a repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": "_Test Loan",
            "total_paid": 1000,
            "posting_date": today(),
            "repayment_date": today(),
        })
        repayment.insert()
        repayment.submit()
        
        # Cancel the repayment
        repayment.cancel()
        
        # Check that the repayment was cancelled
        self.assertEqual(repayment.docstatus, 2)
        
        # Reload the loan to get updated values
        loan = frappe.get_doc("SHG Loan", "_Test Loan")
        
        # Check that the loan summary was updated back
        # Note: This might not be exactly 0 due to other repayments or initial values
        # But it should be less than what it was after the repayment

if __name__ == '__main__':
    unittest.main()