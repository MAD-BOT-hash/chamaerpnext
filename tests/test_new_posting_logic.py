import frappe
import unittest
from frappe.utils import today, add_days

class TestNewPostingLogic(unittest.TestCase):
    """Test the new posting logic according to requirements"""
    
    def setUp(self):
        """Set up test dependencies"""
        # Create a test member
        if not frappe.db.exists("SHG Member", "TEST-MEMBER-001"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "Test Member",
                "id_number": "TEST-MEMBER-001",
                "phone_number": "0700000000"
            })
            member.insert()
        
        # Update SHG Settings to use our new defaults
        settings = frappe.get_single("SHG Settings")
        settings.loan_disbursement_posting_method = "Payment Entry"
        settings.loan_repayment_posting_method = "Payment Entry"
        settings.meeting_fine_posting_method = "Payment Entry"
        settings.contribution_posting_method = "Journal Entry"
        settings.save()
    
    def test_loan_disbursement_creates_payment_entry_with_reference(self):
        """Test that loan disbursement creates Payment Entry with reference no/date"""
        # Create a loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "application_date": today(),
            "disbursement_date": today(),
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Verify that a Payment Entry was created (not a Journal Entry)
        self.assertIsNotNone(loan.disbursement_payment_entry, "Payment Entry should be created for loan disbursement")
        self.assertIsNone(loan.disbursement_journal_entry, "No Journal Entry should be created for loan disbursement")
        
        # Verify the Payment Entry has reference fields filled
        pe = frappe.get_doc("Payment Entry", loan.disbursement_payment_entry)
        self.assertEqual(pe.reference_no, loan.name, "Reference No should be set to loan name")
        self.assertEqual(pe.reference_date, loan.disbursement_date, "Reference Date should be set to disbursement date")
        
        print(f"✓ Loan Disbursement creates Payment Entry: {pe.name}")
        print(f"  Reference No: {pe.reference_no}")
        print(f"  Reference Date: {pe.reference_date}")
    
    def test_loan_repayment_creates_payment_entry(self):
        """Test that loan repayment creates Payment Entry"""
        # First create a loan to repay
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
            "loan_amount": 5000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 6,
            "repayment_frequency": "Monthly",
            "application_date": today(),
            "disbursement_date": today(),
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Create a repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "repayment_date": add_days(today(), 30),
            "total_paid": 1000
        })
        repayment.insert()
        repayment.submit()
        
        # Verify that a Payment Entry was created (not a Journal Entry)
        self.assertIsNotNone(repayment.payment_entry, "Payment Entry should be created for loan repayment")
        self.assertIsNone(repayment.journal_entry, "No Journal Entry should be created for loan repayment")
        
        # Verify the Payment Entry has reference fields filled
        pe = frappe.get_doc("Payment Entry", repayment.payment_entry)
        self.assertEqual(pe.reference_no, repayment.name, "Reference No should be set to repayment name")
        self.assertEqual(pe.reference_date, repayment.repayment_date, "Reference Date should be set to repayment date")
        
        print(f"✓ Loan Repayment creates Payment Entry: {pe.name}")
        print(f"  Reference No: {pe.reference_no}")
        print(f"  Reference Date: {pe.reference_date}")
    
    def test_meeting_fine_creates_payment_entry(self):
        """Test that meeting fine creates Payment Entry"""
        # Create a meeting fine
        fine = frappe.get_doc({
            "doctype": "SHG Meeting Fine",
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
            "fine_date": today(),
            "fine_amount": 100,
            "reason": "Late arrival"
        })
        fine.insert()
        fine.submit()
        
        # Verify that a Payment Entry was created (not a Journal Entry)
        self.assertIsNotNone(fine.payment_entry, "Payment Entry should be created for meeting fine")
        self.assertIsNone(fine.journal_entry, "No Journal Entry should be created for meeting fine")
        
        # Verify the Payment Entry has reference fields filled
        pe = frappe.get_doc("Payment Entry", fine.payment_entry)
        self.assertEqual(pe.reference_no, fine.name, "Reference No should be set to fine name")
        self.assertEqual(pe.reference_date, fine.fine_date, "Reference Date should be set to fine date")
        
        print(f"✓ Meeting Fine creates Payment Entry: {pe.name}")
        print(f"  Reference No: {pe.reference_no}")
        print(f"  Reference Date: {pe.reference_date}")
    
    def test_contribution_creates_journal_entry_without_reference(self):
        """Test that contribution creates Journal Entry without reference fields"""
        # Create a contribution
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
            "contribution_date": today(),
            "amount": 500
        })
        contribution.insert()
        contribution.submit()
        
        # Verify that a Journal Entry was created (not a Payment Entry)
        self.assertIsNotNone(contribution.journal_entry, "Journal Entry should be created for contribution")
        self.assertIsNone(contribution.payment_entry, "No Payment Entry should be created for contribution")
        
        # Verify the Journal Entry does NOT have reference fields filled
        je = frappe.get_doc("Journal Entry", contribution.journal_entry)
        self.assertIsNone(je.reference_no, "Reference No should NOT be set for contribution JE")
        self.assertIsNone(je.reference_date, "Reference Date should NOT be set for contribution JE")
        
        print(f"✓ Contribution creates Journal Entry without reference: {je.name}")
        print(f"  Reference No: {je.reference_no}")
        print(f"  Reference Date: {je.reference_date}")

if __name__ == "__main__":
    unittest.main()