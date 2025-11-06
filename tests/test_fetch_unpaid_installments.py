import unittest
import frappe
from frappe.utils import today
from frappe.tests.utils import FrappeTestCase

class TestFetchUnpaidInstallments(FrappeTestCase):
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
                "interest_type": "Flat Rate",
                "loan_period_months": 3,
                "repayment_frequency": "Monthly",
                "repayment_start_date": today(),
                "company": frappe.db.get_single_value("SHG Settings", "company") or "_Test Company"
            })
            loan.insert()
            loan.submit()
            self.loan = loan.name
        else:
            self.loan = "_Test Loan"

    def tearDown(self):
        # Clean up test data
        if frappe.db.exists("SHG Loan Repayment", {"loan": self.loan}):
            repayment = frappe.get_doc("SHG Loan Repayment", {"loan": self.loan})
            if repayment.docstatus == 1:
                repayment.cancel()
            repayment.delete()
            
        if frappe.db.exists("SHG Loan", self.loan):
            loan = frappe.get_doc("SHG Loan", self.loan)
            if loan.docstatus == 1:
                loan.cancel()
            loan.delete()
            
        if frappe.db.exists("SHG Member", "_Test Member"):
            member = frappe.get_doc("SHG Member", "_Test Member")
            member.delete()

    def test_fetch_unpaid_installments(self):
        """Test fetching unpaid installments into repayment document."""
        # Create a repayment document
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": today(),
            "repayment_date": today(),
            "total_paid": 3000
        })
        repayment.insert(ignore_permissions=True)
        
        # Fetch unpaid installments
        result = repayment.get_unpaid_installments()
        
        # Should have 3 installments
        self.assertEqual(len(result), 3)
        
        # Check that each installment has the required fields
        for installment in result:
            self.assertIsNotNone(installment.installment_no)
            self.assertIsNotNone(installment.due_date)
            self.assertIsNotNone(installment.principal_amount)
            self.assertIsNotNone(installment.interest_amount)
            self.assertIsNotNone(installment.total_due)
            self.assertIsNotNone(installment.unpaid_balance)
            self.assertIsNotNone(installment.status)
            self.assertIsNotNone(installment.schedule_row_id)

    def test_fetch_unpaid_installments_client_script(self):
        """Test that the client script can fetch unpaid installments."""
        # Create a repayment document
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": today(),
            "repayment_date": today(),
            "total_paid": 3000
        })
        repayment.insert(ignore_permissions=True)
        
        # Simulate the client script call
        result = repayment.get_unpaid_installments()
        
        # Check that the installment_adjustment table is populated
        self.assertEqual(len(repayment.installment_adjustment), 3)
        
        # Check that each row has the correct fields
        for row in repayment.installment_adjustment:
            self.assertIsNotNone(row.installment_no)
            self.assertIsNotNone(row.due_date)
            self.assertIsNotNone(row.principal_amount)
            self.assertIsNotNone(row.interest_amount)
            self.assertIsNotNone(row.total_due)
            self.assertIsNotNone(row.unpaid_balance)
            self.assertIsNotNone(row.status)
            self.assertIsNotNone(row.schedule_row_id)

if __name__ == '__main__':
    unittest.main()