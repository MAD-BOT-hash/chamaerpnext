import frappe
import unittest
from frappe.utils import flt, today

class TestInstallmentRepayment(unittest.TestCase):
    """Test installment-based repayment functionality."""
    
    def setUp(self):
        """Set up test loan with repayment schedule."""
        # Create a test member
        if not frappe.db.exists("SHG Member", "Test Member - Installment Repayment"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "Test Member - Installment Repayment",
                "membership_status": "Active"
            })
            member.insert(ignore_permissions=True)
            self.member = member.name
        else:
            self.member = "Test Member - Installment Repayment"
        
        # Create a test loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": self.member,
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 3,
            "posting_date": "2025-01-01",
            "application_date": "2025-01-01",
            "disbursement_date": "2025-01-01",
            "repayment_start_date": "2025-02-01",
            "status": "Disbursed"
        })
        loan.insert(ignore_permissions=True)
        loan.submit()
        self.loan = loan.name
        
        # Create repayment schedule
        from shg.shg.api.loan import generate_schedule
        generate_schedule(self.loan)
    
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
    
    def test_pull_unpaid_installments(self):
        """Test pulling unpaid installments into repayment document."""
        # Create a repayment document
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": today(),
            "repayment_date": today(),
            "total_paid": 3500
        })
        repayment.insert(ignore_permissions=True)
        
        # Pull unpaid installments
        repayment.pull_unpaid_installments()
        
        # Should have 3 installments
        self.assertEqual(len(repayment.installment_adjustment), 3)
        
        # Each installment should have correct data
        for i, installment in enumerate(repayment.installment_adjustment):
            self.assertEqual(installment.installment_no, i + 1)
            self.assertEqual(installment.total_due, 3733.33)  # 10000/3 + (10000*0.12*3/12)/3
            self.assertEqual(installment.remaining, 3733.33)
            self.assertEqual(installment.amount_to_repay, 0)
    
    def test_installment_based_repayment(self):
        """Test repayment using installment adjustments."""
        # Create a repayment document
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": today(),
            "repayment_date": today(),
            "total_paid": 3733.33
        })
        repayment.insert(ignore_permissions=True)
        
        # Pull unpaid installments
        repayment.pull_unpaid_installments()
        
        # Set amount to repay for first installment
        repayment.installment_adjustment[0].amount_to_repay = 3733.33
        repayment.save(ignore_permissions=True)
        
        # Submit the repayment
        repayment.submit()
        
        # Check that the schedule was updated
        schedule_row = frappe.get_doc("SHG Loan Repayment Schedule", repayment.installment_adjustment[0].schedule_row_id)
        self.assertEqual(schedule_row.amount_paid, 3733.33)
        self.assertEqual(schedule_row.unpaid_balance, 0)
        self.assertEqual(schedule_row.status, "Paid")
    
    def test_partial_installment_repayment(self):
        """Test partial repayment of an installment."""
        # Create a repayment document
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": today(),
            "repayment_date": today(),
            "total_paid": 2000
        })
        repayment.insert(ignore_permissions=True)
        
        # Pull unpaid installments
        repayment.pull_unpaid_installments()
        
        # Set partial amount to repay for first installment
        repayment.installment_adjustment[0].amount_to_repay = 2000
        repayment.save(ignore_permissions=True)
        
        # Submit the repayment
        repayment.submit()
        
        # Check that the schedule was updated
        schedule_row = frappe.get_doc("SHG Loan Repayment Schedule", repayment.installment_adjustment[0].schedule_row_id)
        self.assertEqual(schedule_row.amount_paid, 2000)
        self.assertEqual(schedule_row.unpaid_balance, 1733.33)
        self.assertEqual(schedule_row.status, "Partially Paid")
    
    def test_multiple_installment_repayment(self):
        """Test repayment across multiple installments."""
        # Create a repayment document
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": self.loan,
            "posting_date": today(),
            "repayment_date": today(),
            "total_paid": 5000
        })
        repayment.insert(ignore_permissions=True)
        
        # Pull unpaid installments
        repayment.pull_unpaid_installments()
        
        # Set amounts to repay for first two installments
        repayment.installment_adjustment[0].amount_to_repay = 3733.33  # Full payment
        repayment.installment_adjustment[1].amount_to_repay = 1266.67  # Partial payment
        repayment.save(ignore_permissions=True)
        
        # Submit the repayment
        repayment.submit()
        
        # Check that the first schedule row was updated
        schedule_row_1 = frappe.get_doc("SHG Loan Repayment Schedule", repayment.installment_adjustment[0].schedule_row_id)
        self.assertEqual(schedule_row_1.amount_paid, 3733.33)
        self.assertEqual(schedule_row_1.unpaid_balance, 0)
        self.assertEqual(schedule_row_1.status, "Paid")
        
        # Check that the second schedule row was updated
        schedule_row_2 = frappe.get_doc("SHG Loan Repayment Schedule", repayment.installment_adjustment[1].schedule_row_id)
        self.assertEqual(schedule_row_2.amount_paid, 1266.67)
        self.assertEqual(schedule_row_2.unpaid_balance, 2466.66)
        self.assertEqual(schedule_row_2.status, "Partially Paid")

if __name__ == '__main__':
    unittest.main()