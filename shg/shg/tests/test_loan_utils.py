import unittest
import frappe
from frappe.utils import today, add_days
from shg.shg.utils.loan_utils import flag_overdue_loans

class TestLoanUtils(unittest.TestCase):
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
            self.loan_name = loan.name
        else:
            self.loan_name = "_Test Loan"

    def tearDown(self):
        # Clean up test data
        if frappe.db.exists("SHG Loan", "_Test Loan"):
            loan = frappe.get_doc("SHG Loan", "_Test Loan")
            if loan.docstatus == 1:
                loan.cancel()
            loan.delete()

        if frappe.db.exists("SHG Member", "_Test Member"):
            member = frappe.get_doc("SHG Member", "_Test Member")
            member.delete()

    def test_flag_overdue_loans(self):
        """Test flagging overdue loan installments."""
        # First generate schedule
        from shg.shg.api.loan import generate_schedule
        generate_schedule(self.loan_name)
        
        # Submit the loan
        loan = frappe.get_doc("SHG Loan", self.loan_name)
        loan.submit()
        
        # Manually set the first installment's due date to past to make it overdue
        loan.reload()
        if loan.repayment_schedule:
            first_installment = loan.repayment_schedule[0]
            first_installment.due_date = add_days(today(), -10)  # 10 days ago
            first_installment.save()
        
        # Run the overdue flagging function
        flag_overdue_loans()
        
        # Check that the installment is now flagged as overdue
        loan.reload()
        if loan.repayment_schedule:
            first_installment = loan.repayment_schedule[0]
            self.assertEqual(first_installment.status, "Overdue")

if __name__ == '__main__':
    unittest.main()