import frappe
import unittest
from frappe.utils import today, add_months

class TestSHGLoanRepayment(unittest.TestCase):
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

    def test_loan_repayment_schedule_creation(self):
        """Test that repayment schedule is created correctly"""
        loan = frappe.get_doc("SHG Loan", "_Test Loan")
        
        # Check that schedule was created
        self.assertTrue(len(loan.repayment_schedule) > 0)
        
        # Check that total payable matches loan amount plus interest
        self.assertGreater(loan.total_payable, loan.loan_amount)
        
        # Check that all installments have due dates
        for installment in loan.repayment_schedule:
            self.assertIsNotNone(installment.due_date)

    def test_loan_repayment_summary_refresh(self):
        """Test that repayment summary refresh works correctly"""
        from shg.shg.doctype.shg_loan.api import refresh_repayment_summary
        
        loan = frappe.get_doc("SHG Loan", "_Test Loan")
        
        # Initially, total_repaid should be 0
        self.assertEqual(loan.total_repaid, 0)
        
        # Create a repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": "_Test Loan",
            "total_paid": 1000,
            "posting_date": today(),
        })
        repayment.insert()
        repayment.submit()
        
        # Refresh the loan summary
        refresh_repayment_summary(loan.name)
        
        # Reload the loan to get updated values
        loan.reload()
        
        # Check that total_repaid has been updated
        self.assertEqual(loan.total_repaid, 1000)
        
        # Check that balance_amount has been reduced
        self.assertLess(loan.balance_amount, loan.total_payable)

    def test_loan_repayment_schedule_updates(self):
        """Test that repayment schedule rows are updated correctly when repayment is made"""
        loan = frappe.get_doc("SHG Loan", "_Test Loan")
        
        # Create a repayment for the first installment
        first_installment = loan.repayment_schedule[0]
        repayment_amount = first_installment.total_payment
        
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": "_Test Loan",
            "total_paid": repayment_amount,
            "posting_date": today(),
        })
        repayment.insert()
        repayment.submit()
        
        # Reload the loan to get updated values
        loan.reload()
        
        # Check that the first installment status is updated
        updated_first_installment = loan.repayment_schedule[0]
        self.assertEqual(updated_first_installment.status, "Paid")
        self.assertEqual(updated_first_installment.amount_paid, repayment_amount)
        self.assertEqual(updated_first_installment.unpaid_balance, 0)

if __name__ == '__main__':
    unittest.main()