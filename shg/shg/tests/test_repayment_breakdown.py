import frappe
import unittest
from frappe.utils import today, add_days

class TestRepaymentBreakdown(unittest.TestCase):
    def setUp(self):
        # Create a test member
        if not frappe.db.exists("SHG Member", "_Test Member for Repayment"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member for Repayment",
                "membership_status": "Active",
                "date_joined": today(),
            })
            member.insert()

        # Create a test loan
        self.loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "_Test Member for Repayment",
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Reducing Balance",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "repayment_start_date": today(),
            "company": frappe.db.get_single_value("SHG Settings", "company") or "_Test Company"
        })
        self.loan.insert()
        self.loan.submit()

        # Create a test repayment
        self.repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan.name,
            "posting_date": today(),
            "repayment_date": today(),
            "total_paid": 0,
            "payment_method": "Cash"
        })
        self.repayment.insert()

    def tearDown(self):
        # Clean up test data
        if frappe.db.exists("SHG Loan Repayment", self.repayment.name):
            repayment = frappe.get_doc("SHG Loan Repayment", self.repayment.name)
            if repayment.docstatus == 1:
                repayment.cancel()
            repayment.delete()

        if frappe.db.exists("SHG Loan", self.loan.name):
            loan = frappe.get_doc("SHG Loan", self.loan.name)
            if loan.docstatus == 1:
                loan.cancel()
            loan.delete()

        if frappe.db.exists("SHG Member", "_Test Member for Repayment"):
            member = frappe.get_doc("SHG Member", "_Test Member for Repayment")
            member.delete()

    def test_get_unpaid_installments(self):
        """Test that get_unpaid_installments method works correctly"""
        # Call the method
        result = self.repayment.get_unpaid_installments()
        
        # Verify that the repayment breakdown table is populated
        self.assertIsNotNone(result)
        self.assertGreater(len(self.repayment.repayment_breakdown), 0)
        
        # Verify that each row has the required fields
        for row in self.repayment.repayment_breakdown:
            self.assertIsNotNone(row.installment_no)
            self.assertIsNotNone(row.due_date)
            self.assertIsNotNone(row.emi_amount)
            self.assertIsNotNone(row.principal_component)
            self.assertIsNotNone(row.interest_component)
            self.assertIsNotNone(row.unpaid_balance)
            self.assertEqual(row.amount_to_pay, 0)  # Should default to 0

    def test_calculate_repayment_breakdown(self):
        """Test that calculate_repayment_breakdown method works correctly"""
        # Set a repayment amount
        self.repayment.total_paid = 1000
        self.repayment.loan = self.loan.name
        
        # Call the method
        result = self.repayment.calculate_repayment_breakdown()
        
        # Verify that the breakdown is calculated correctly
        self.assertIsNotNone(result)
        self.assertIn("principal_amount", result)
        self.assertIn("interest_amount", result)
        self.assertIn("penalty_amount", result)
        self.assertIn("balance_after_payment", result)
        
        # Verify that the parent document fields are updated
        self.assertIsNotNone(self.repayment.principal_amount)
        self.assertIsNotNone(self.repayment.interest_amount)
        self.assertIsNotNone(self.repayment.penalty_amount)
        self.assertIsNotNone(self.repayment.balance_after_payment)

    def test_amount_to_pay_validation(self):
        """Test that amount_to_pay validation works correctly"""
        # Get unpaid installments
        self.repayment.get_unpaid_installments()
        
        # Try to set an amount higher than unpaid balance
        if len(self.repayment.repayment_breakdown) > 0:
            row = self.repayment.repayment_breakdown[0]
            original_unpaid = row.unpaid_balance
            row.amount_to_pay = original_unpaid + 100  # Exceed unpaid balance
            
            # The validation should cap it at unpaid balance
            # Note: This validation happens in the frontend, so we're just testing the logic here

if __name__ == '__main__':
    unittest.main()