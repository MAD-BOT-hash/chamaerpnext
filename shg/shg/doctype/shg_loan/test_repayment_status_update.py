import frappe
import unittest
from frappe.utils import nowdate, add_days

class TestRepaymentStatusUpdate(unittest.TestCase):
    def setUp(self):
        # Create a test loan with repayment schedule
        self.loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "_Test SHG Member",
            "loan_amount": 10000,
            "interest_rate": 12,
            "loan_period_months": 12,
            "repayment_start_date": nowdate()
        })
        self.loan.insert()
        self.loan.submit()
        
    def tearDown(self):
        frappe.delete_doc("SHG Loan", self.loan.name)
        
    def test_repayment_status_update(self):
        # Test that recalculate_summary updates statuses correctly
        loan_doc = frappe.get_doc("SHG Loan", self.loan.name)
        
        # Make first installment paid
        if loan_doc.repayment_schedule:
            loan_doc.repayment_schedule[0].amount_paid = loan_doc.repayment_schedule[0].total_payment
            loan_doc.save()
            
        # Recalculate summary
        log_entries = loan_doc.recalculate_summary()
        
        # Verify that the first installment is marked as Paid
        self.assertEqual(loan_doc.repayment_schedule[0].status, "Paid")
        
        # Verify log entry was created
        self.assertTrue(len(log_entries) > 0)
        
    def test_overdue_status(self):
        # Test that overdue status is set correctly
        loan_doc = frappe.get_doc("SHG Loan", self.loan.name)
        
        # Set due date to past
        if loan_doc.repayment_schedule:
            loan_doc.repayment_schedule[0].due_date = add_days(nowdate(), -30)
            loan_doc.save()
            
        # Recalculate summary
        log_entries = loan_doc.recalculate_summary()
        
        # Verify that the installment is marked as Overdue
        self.assertEqual(loan_doc.repayment_schedule[0].status, "Overdue")