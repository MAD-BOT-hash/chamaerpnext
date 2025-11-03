import unittest
import frappe
from frappe.utils import today, add_months
from shg.shg.api.loan import generate_schedule, refresh_repayment_summary, get_member_loan_statement, mark_installment_paid

class TestLoanAPI(unittest.TestCase):
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

    def test_generate_schedule(self):
        """Test generation of loan repayment schedule."""
        # Generate schedule
        result = generate_schedule(self.loan_name)
        
        # Check result
        self.assertEqual(result["status"], "success")
        
        # Reload loan to check schedule
        loan = frappe.get_doc("SHG Loan", self.loan_name)
        self.assertGreater(len(loan.repayment_schedule), 0)
        
        # Check that all required fields are present
        for row in loan.repayment_schedule:
            self.assertIsNotNone(row.installment_no)
            self.assertIsNotNone(row.due_date)
            self.assertIsNotNone(row.principal_component)
            self.assertIsNotNone(row.interest_component)
            self.assertIsNotNone(row.total_payment)
            self.assertIsNotNone(row.loan_balance)
            self.assertEqual(row.status, "Pending")

    def test_refresh_repayment_summary(self):
        """Test refreshing loan repayment summary."""
        # First generate schedule
        generate_schedule(self.loan_name)
        
        # Refresh summary
        result = refresh_repayment_summary(self.loan_name)
        
        # Check that summary fields are populated
        loan = frappe.get_doc("SHG Loan", self.loan_name)
        self.assertGreater(loan.total_payable, 0)
        self.assertEqual(loan.total_repaid, 0)
        self.assertEqual(loan.balance_amount, loan.total_payable)
        self.assertEqual(loan.overdue_amount, 0)

    def test_get_member_loan_statement(self):
        """Test getting member loan statement."""
        # First generate schedule
        generate_schedule(self.loan_name)
        
        # Get statement by loan name
        result = get_member_loan_statement(loan_name=self.loan_name)
        
        # Check result structure
        self.assertIn("loan_details", result)
        self.assertIn("repayment_schedule", result)
        self.assertIn("count", result)
        
        # Check loan details
        loan_details = result["loan_details"]
        self.assertEqual(loan_details["loan_id"], self.loan_name)
        self.assertEqual(loan_details["member_name"], "_Test Member")
        
        # Get statement by member
        result = get_member_loan_statement(member="_Test Member")
        self.assertIn("loan_details", result)

    def test_mark_installment_paid(self):
        """Test marking an installment as paid."""
        # First generate schedule
        generate_schedule(self.loan_name)
        
        # Get the first installment
        loan = frappe.get_doc("SHG Loan", self.loan_name)
        first_installment = loan.repayment_schedule[0]
        
        # Mark as paid
        result = mark_installment_paid(self.loan_name, first_installment.name, first_installment.total_payment)
        
        # Check result
        self.assertEqual(result["status"], "success")
        
        # Reload and check that installment is marked as paid
        updated_installment = frappe.get_doc("SHG Loan Repayment Schedule", first_installment.name)
        self.assertEqual(updated_installment.status, "Paid")
        self.assertEqual(updated_installment.amount_paid, first_installment.total_payment)
        self.assertEqual(updated_installment.unpaid_balance, 0)

if __name__ == '__main__':
    unittest.main()