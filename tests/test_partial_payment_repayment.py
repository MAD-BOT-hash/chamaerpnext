import unittest
import frappe
from frappe.utils import today, add_months
from frappe.tests.utils import FrappeTestCase

class TestPartialPaymentRepayment(FrappeTestCase):
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
        repayment.get_unpaid_installments()
        
        # Should have 3 installments
        self.assertEqual(len(repayment.installment_adjustment), 3)
        
        # Each installment should have correct data
        for i, installment in enumerate(repayment.installment_adjustment):
            self.assertEqual(installment.installment_no, i + 1)
            self.assertEqual(installment.status, "Pending")
            self.assertEqual(installment.unpaid_balance, installment.total_due)
            self.assertEqual(installment.amount_to_repay, 0)

    def test_partial_installment_repayment(self):
        """Test partial repayment of installments."""
        # Create a repayment document
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": today(),
            "repayment_date": today(),
            "total_paid": 1000
        })
        repayment.insert(ignore_permissions=True)
        
        # Fetch unpaid installments
        repayment.get_unpaid_installments()
        
        # Set partial payment for first installment
        repayment.installment_adjustment[0].amount_to_repay = 1000
        repayment.save()
        
        # Submit the repayment
        repayment.submit()
        
        # Check that the installment status is updated
        loan = frappe.get_doc("SHG Loan", self.loan)
        schedule_row = loan.repayment_schedule[0]
        self.assertEqual(schedule_row.status, "Partially Paid")
        self.assertEqual(schedule_row.amount_paid, 1000)
        self.assertGreater(schedule_row.unpaid_balance, 0)

    def test_full_installment_repayment(self):
        """Test full repayment of an installment."""
        # Get the loan to determine installment amount
        loan = frappe.get_doc("SHG Loan", self.loan)
        installment_amount = loan.repayment_schedule[0].total_due
        
        # Create a repayment document
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": today(),
            "repayment_date": today(),
            "total_paid": installment_amount
        })
        repayment.insert(ignore_permissions=True)
        
        # Fetch unpaid installments
        repayment.get_unpaid_installments()
        
        # Set full payment for first installment
        repayment.installment_adjustment[0].amount_to_repay = installment_amount
        repayment.save()
        
        # Submit the repayment
        repayment.submit()
        
        # Check that the installment status is updated
        loan.reload()
        schedule_row = loan.repayment_schedule[0]
        self.assertEqual(schedule_row.status, "Paid")
        self.assertEqual(schedule_row.amount_paid, installment_amount)
        self.assertEqual(schedule_row.unpaid_balance, 0)

    def test_multiple_installment_repayment(self):
        """Test repayment across multiple installments."""
        # Get the loan to determine installment amounts
        loan = frappe.get_doc("SHG Loan", self.loan)
        first_installment = loan.repayment_schedule[0].total_due
        second_installment = loan.repayment_schedule[1].total_due
        
        # Create a repayment document for partial first and full second installment
        total_payment = (first_installment / 2) + second_installment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": today(),
            "repayment_date": today(),
            "total_paid": total_payment
        })
        repayment.insert(ignore_permissions=True)
        
        # Fetch unpaid installments
        repayment.get_unpaid_installments()
        
        # Set payments for first two installments
        repayment.installment_adjustment[0].amount_to_repay = first_installment / 2
        repayment.installment_adjustment[1].amount_to_repay = second_installment
        repayment.save()
        
        # Submit the repayment
        repayment.submit()
        
        # Check that the installment statuses are updated correctly
        loan.reload()
        first_schedule_row = loan.repayment_schedule[0]
        second_schedule_row = loan.repayment_schedule[1]
        
        self.assertEqual(first_schedule_row.status, "Partially Paid")
        self.assertEqual(first_schedule_row.amount_paid, first_installment / 2)
        self.assertGreater(first_schedule_row.unpaid_balance, 0)
        
        self.assertEqual(second_schedule_row.status, "Paid")
        self.assertEqual(second_schedule_row.amount_paid, second_installment)
        self.assertEqual(second_schedule_row.unpaid_balance, 0)

if __name__ == '__main__':
    unittest.main()