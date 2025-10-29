import frappe
import unittest
from frappe.utils import today, add_months

class TestRepaymentSchedule(unittest.TestCase):
    def setUp(self):
        # Create a test member if it doesn't exist
        if not frappe.db.exists("SHG Member", "_Test Member"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member",
                "membership_status": "Active",
                "total_contributions": 5000
            })
            member.insert()

    def tearDown(self):
        # Clean up test data
        if frappe.db.exists("SHG Loan", {"member": "_Test Member"}):
            loans = frappe.get_all("SHG Loan", filters={"member": "_Test Member"})
            for loan in loans:
                frappe.delete_doc("SHG Loan", loan.name)
        
        if frappe.db.exists("SHG Member", "_Test Member"):
            frappe.delete_doc("SHG Member", "_Test Member")

    def test_flat_rate_repayment_schedule(self):
        """Test generation of repayment schedule with flat interest rate."""
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "_Test Member",
            "member_name": "_Test Member",
            "loan_amount": 10000,
            "interest_rate": 12,  # 12% per annum
            "interest_type": "Flat Rate",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "application_date": today(),
            "disbursement_date": today(),
            "repayment_start_date": add_months(today(), 1)
        })
        loan.insert()
        
        # Generate repayment schedule
        loan.create_repayment_schedule_if_needed()
        
        # Check that schedule was generated
        self.assertEqual(len(loan.repayment_schedule), 12)
        
        # Check first installment
        first_installment = loan.repayment_schedule[0]
        self.assertEqual(first_installment.installment_no, 1)
        self.assertEqual(first_installment.status, "Pending")
        
        # For flat rate: Total interest = 10000 * 12% * 1 = 1200
        # Monthly installment = (10000 + 1200) / 12 = 933.33
        # Principal component = 10000 / 12 = 833.33
        # Interest component = 1200 / 12 = 100
        self.assertAlmostEqual(first_installment.principal_amount, 833.33, places=2)
        self.assertAlmostEqual(first_installment.interest_amount, 100.00, places=2)
        self.assertAlmostEqual(first_installment.total_due, 933.33, places=2)

    def test_reducing_balance_repayment_schedule(self):
        """Test generation of repayment schedule with reducing balance method."""
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "_Test Member",
            "member_name": "_Test Member",
            "loan_amount": 10000,
            "interest_rate": 12,  # 12% per annum
            "interest_type": "Reducing Balance",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "application_date": today(),
            "disbursement_date": today(),
            "repayment_start_date": add_months(today(), 1)
        })
        loan.insert()
        
        # Generate repayment schedule
        loan.create_repayment_schedule_if_needed()
        
        # Check that schedule was generated
        self.assertEqual(len(loan.repayment_schedule), 12)
        
        # Check first installment
        first_installment = loan.repayment_schedule[0]
        self.assertEqual(first_installment.installment_no, 1)
        self.assertEqual(first_installment.status, "Pending")
        
        # For reducing balance with 12% annual rate:
        # Monthly rate = 1% (12%/12)
        # EMI = 10000 * 0.01 * (1.01^12) / (1.01^12 - 1) = 888.49
        self.assertAlmostEqual(first_installment.total_due, 888.49, places=2)
        
        # First month interest = 10000 * 0.01 = 100
        self.assertAlmostEqual(first_installment.interest_amount, 100.00, places=2)
        
        # First month principal = 888.49 - 100 = 788.49
        self.assertAlmostEqual(first_installment.principal_amount, 788.49, places=2)

    def test_repayment_schedule_update_with_audit(self):
        """Test that repayment schedule updates when loan terms change with audit log."""
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "_Test Member",
            "member_name": "_Test Member",
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Reducing Balance",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "application_date": today(),
            "disbursement_date": today(),
            "repayment_start_date": add_months(today(), 1)
        })
        loan.insert()
        
        # Generate initial repayment schedule
        loan.create_repayment_schedule_if_needed()
        initial_installments = len(loan.repayment_schedule)
        
        # Change loan terms
        loan.loan_amount = 15000
        loan.loan_period_months = 18
        loan.save()
        
        # Check that schedule was updated
        updated_installments = len(loan.repayment_schedule)
        self.assertEqual(updated_installments, 18)
        
        # Check that audit comment was added
        comments = frappe.get_all("Comment", 
                                filters={"reference_doctype": "SHG Loan", "reference_name": loan.name},
                                fields=["content"])
        audit_comment_found = any("Repayment schedule updated" in comment.content for comment in comments)
        self.assertTrue(audit_comment_found)

if __name__ == '__main__':
    unittest.main()