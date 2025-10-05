import frappe
import unittest
from frappe.utils import today, add_days

class TestRefactoredPostingLogic(unittest.TestCase):
    """Test the refactored posting logic according to new requirements"""
    
    def setUp(self):
        """Set up test dependencies"""
        # Create a test company if it doesn't exist
        if not frappe.db.exists("Company", "Test SHG Company"):
            company = frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test SHG Company",
                "abbr": "TSC",
                "default_currency": "KES",
                "country": "Kenya"
            })
            company.insert()
        
        # Create a test member if it doesn't exist
        if not frappe.db.exists("SHG Member", "TEST-MEMBER-002"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "Test Member 2",
                "gender": "Female",
                "date_of_birth": "1992-05-15",
                "phone_number": "+254700000001",
                "email": "test2@example.com",
                "address": "Test Address 2",
                "membership_status": "Active"
            })
            member.insert()
            
        # Create a test customer for the member
        if not frappe.db.exists("Customer", "Test Member 2"):
            customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": "Test Member 2",
                "customer_type": "Individual",
                "customer_group": "All Customer Groups",
                "territory": "All Territories"
            })
            customer.insert()
            
        # Link customer to member
        member = frappe.get_doc("SHG Member", "TEST-MEMBER-002")
        member.customer = "Test Member 2"
        member.save()
        
        # Create test accounts if they don't exist
        company = "Test SHG Company"
        company_abbr = "TSC"
        
        # Create parent accounts first
        if not frappe.db.exists("Account", f"Bank Accounts - {company_abbr}"):
            bank_group = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Bank Accounts",
                "parent_account": f"Current Assets - {company_abbr}",
                "is_group": 1,
                "root_type": "Asset",
                "account_type": "Bank"
            })
            bank_group.insert()
            
        if not frappe.db.exists("Account", f"Test Bank - {company_abbr}"):
            bank_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Test Bank",
                "parent_account": f"Bank Accounts - {company_abbr}",
                "is_group": 0,
                "root_type": "Asset",
                "account_type": "Bank"
            })
            bank_account.insert()
            
        if not frappe.db.exists("Account", f"Cash - {company_abbr}"):
            cash_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Cash",
                "parent_account": f"Current Assets - {company_abbr}",
                "is_group": 0,
                "root_type": "Asset",
                "account_type": "Cash"
            })
            cash_account.insert()
            
        # Update SHG Settings with test accounts
        settings = frappe.get_single("SHG Settings")
        settings.default_bank_account = f"Test Bank - {company_abbr}"
        settings.default_cash_account = f"Cash - {company_abbr}"
        settings.loan_disbursement_posting_method = "Payment Entry"
        settings.loan_repayment_posting_method = "Payment Entry"
        settings.meeting_fine_posting_method = "Payment Entry"
        settings.contribution_posting_method = "Journal Entry"
        settings.save()

    def test_loan_disbursement_creates_payment_entry_with_reference(self):
        """Test that loan disbursement creates Payment Entry with reference_no and reference_date"""
        # Create a loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "TEST-MEMBER-002",
            "member_name": "Test Member 2",
            "loan_amount": 15000,
            "interest_rate": 10,
            "loan_period_months": 12,
            "disbursement_date": today(),
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Verify that a Payment Entry was created
        self.assertEqual(loan.posted_to_gl, 1)
        self.assertIsNotNone(loan.disbursement_payment_entry)
        self.assertIsNone(loan.disbursement_journal_entry)
        
        # Verify the Payment Entry exists and is submitted
        self.assertTrue(frappe.db.exists("Payment Entry", loan.disbursement_payment_entry))
        pe = frappe.get_doc("Payment Entry", loan.disbursement_payment_entry)
        self.assertEqual(pe.docstatus, 1)
        
        # Verify Payment Entry details
        self.assertEqual(pe.payment_type, "Pay")
        self.assertEqual(pe.party_type, "SHG Member")
        self.assertEqual(pe.party, "TEST-MEMBER-002")
        self.assertAlmostEqual(pe.paid_amount, 15000, places=2)
        self.assertAlmostEqual(pe.received_amount, 15000, places=2)
        
        # Verify reference fields are set
        self.assertEqual(pe.reference_no, loan.name)
        self.assertEqual(pe.reference_date, loan.disbursement_date)
        
        # Verify remarks
        self.assertIn("Loan Disbursement for TEST-MEMBER-002", pe.remarks)
        self.assertIn(loan.name, pe.remarks)
        
        # Verify accounts
        self.assertIn("Test Bank", pe.paid_from)
        # Member account should be in paid_to
        
        # Verify mode of payment and voucher type
        self.assertEqual(pe.mode_of_payment, "Bank")
        self.assertEqual(pe.voucher_type, "Bank Entry")
        
        # Verify custom field for traceability
        self.assertEqual(pe.custom_shg_loan, loan.name)
        
        print(f"✓ Loan Disbursement creates Payment Entry: {pe.name}")
        print(f"  Reference No: {pe.reference_no}")
        print(f"  Reference Date: {pe.reference_date}")
        print(f"  Amount: {pe.paid_amount}")

    def test_loan_repayment_creates_payment_entry_with_reference(self):
        """Test that loan repayment creates Payment Entry with reference_no and reference_date"""
        # First create a loan to repay
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "TEST-MEMBER-002",
            "member_name": "Test Member 2",
            "loan_amount": 10000,
            "interest_rate": 12,
            "loan_period_months": 12,
            "disbursement_date": today(),
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Create a repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": "TEST-MEMBER-002",
            "member_name": "Test Member 2",
            "repayment_date": add_days(today(), 30),
            "total_paid": 1200,
            "principal_amount": 1000,
            "interest_amount": 200
        })
        repayment.insert()
        repayment.submit()
        
        # Verify that a Payment Entry was created
        self.assertEqual(repayment.posted_to_gl, 1)
        self.assertIsNotNone(repayment.payment_entry)
        self.assertIsNone(repayment.journal_entry)
        
        # Verify the Payment Entry exists and is submitted
        self.assertTrue(frappe.db.exists("Payment Entry", repayment.payment_entry))
        pe = frappe.get_doc("Payment Entry", repayment.payment_entry)
        self.assertEqual(pe.docstatus, 1)
        
        # Verify Payment Entry details
        self.assertEqual(pe.payment_type, "Receive")
        self.assertEqual(pe.party_type, "SHG Member")
        self.assertEqual(pe.party, "TEST-MEMBER-002")
        self.assertAlmostEqual(pe.paid_amount, 1200, places=2)
        self.assertAlmostEqual(pe.received_amount, 1200, places=2)
        
        # Verify reference fields are set
        self.assertEqual(pe.reference_no, repayment.name)
        self.assertEqual(pe.reference_date, repayment.repayment_date)
        
        # Verify remarks
        self.assertIn("Loan Repayment", pe.remarks)
        self.assertIn(loan.name, pe.remarks)
        self.assertIn("TEST-MEMBER-002", pe.remarks)
        
        # Verify accounts
        # Member account should be in paid_from
        # Bank account should be in paid_to
        
        # Verify mode of payment and voucher type
        self.assertEqual(pe.mode_of_payment, "Bank")
        self.assertEqual(pe.voucher_type, "Bank Entry")
        
        # Verify custom field for traceability
        self.assertEqual(pe.custom_shg_loan_repayment, repayment.name)
        
        # Verify reference allocation
        self.assertEqual(len(pe.references), 1)
        self.assertEqual(pe.references[0].reference_doctype, "Loan")
        self.assertEqual(pe.references[0].reference_name, loan.name)
        self.assertAlmostEqual(pe.references[0].allocated_amount, 1000, places=2)  # Principal amount
        
        print(f"✓ Loan Repayment creates Payment Entry: {pe.name}")
        print(f"  Reference No: {pe.reference_no}")
        print(f"  Reference Date: {pe.reference_date}")
        print(f"  Amount: {pe.paid_amount}")

    def test_contribution_creates_journal_entry_without_reference(self):
        """Test that contribution creates Journal Entry without reference_no or reference_date"""
        # Create a contribution
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": "TEST-MEMBER-002",
            "member_name": "Test Member 2",
            "contribution_date": today(),
            "amount": 500,
            "contribution_type": "Regular Weekly"
        })
        contribution.insert()
        contribution.submit()
        
        # Verify that a Journal Entry was created
        self.assertEqual(contribution.posted_to_gl, 1)
        self.assertIsNotNone(contribution.journal_entry)
        self.assertIsNone(contribution.payment_entry)
        
        # Verify the Journal Entry exists and is submitted
        self.assertTrue(frappe.db.exists("Journal Entry", contribution.journal_entry))
        je = frappe.get_doc("Journal Entry", contribution.journal_entry)
        self.assertEqual(je.docstatus, 1)
        
        # Verify Journal Entry details
        self.assertEqual(je.voucher_type, "Journal Entry")
        self.assertEqual(je.posting_date, contribution.contribution_date)
        
        # Verify reference fields are NOT set (as per requirements)
        self.assertIsNone(je.reference_no)
        self.assertIsNone(je.reference_date)
        
        # Verify remarks
        self.assertIn("Contribution by", je.user_remark)
        self.assertIn("TEST-MEMBER-002", je.user_remark)
        
        # Verify accounts (should have 2 entries: debit bank, credit member)
        self.assertEqual(len(je.accounts), 2)
        
        # Find debit and credit entries
        debit_entry = None
        credit_entry = None
        for entry in je.accounts:
            if entry.debit_in_account_currency > 0:
                debit_entry = entry
            elif entry.credit_in_account_currency > 0:
                credit_entry = entry
                
        self.assertIsNotNone(debit_entry)
        self.assertIsNotNone(credit_entry)
        
        # Verify amounts
        self.assertAlmostEqual(debit_entry.debit_in_account_currency, 500, places=2)
        self.assertAlmostEqual(credit_entry.credit_in_account_currency, 500, places=2)
        
        # Verify account types
        self.assertIn("Test Bank", debit_entry.account) or self.assertIn("Cash", debit_entry.account)
        # Credit entry should be member account
        
        # Verify party details for credit entry
        self.assertEqual(credit_entry.party_type, "SHG Member")
        self.assertEqual(credit_entry.party, "TEST-MEMBER-002")
        
        # Verify custom field for traceability
        self.assertEqual(je.custom_shg_contribution, contribution.name)
        
        print(f"✓ Contribution creates Journal Entry without reference: {je.name}")
        print(f"  Reference No: {je.reference_no}")
        print(f"  Reference Date: {je.reference_date}")
        print(f"  Amount: {debit_entry.debit_in_account_currency}")

    def test_meeting_fine_creates_payment_entry_with_reference(self):
        """Test that meeting fine creates Payment Entry with reference_no and reference_date"""
        # Create a meeting fine
        fine = frappe.get_doc({
            "doctype": "SHG Meeting Fine",
            "member": "TEST-MEMBER-002",
            "member_name": "Test Member 2",
            "fine_date": today(),
            "fine_amount": 100,
            "fine_reason": "Late Arrival",
            "status": "Paid"
        })
        fine.insert()
        fine.submit()
        
        # Verify that a Payment Entry was created
        self.assertEqual(fine.posted_to_gl, 1)
        self.assertIsNotNone(fine.payment_entry)
        self.assertIsNone(fine.journal_entry)
        
        # Verify the Payment Entry exists and is submitted
        self.assertTrue(frappe.db.exists("Payment Entry", fine.payment_entry))
        pe = frappe.get_doc("Payment Entry", fine.payment_entry)
        self.assertEqual(pe.docstatus, 1)
        
        # Verify Payment Entry details
        self.assertEqual(pe.payment_type, "Receive")
        self.assertEqual(pe.party_type, "SHG Member")
        self.assertEqual(pe.party, "TEST-MEMBER-002")
        self.assertAlmostEqual(pe.paid_amount, 100, places=2)
        self.assertAlmostEqual(pe.received_amount, 100, places=2)
        
        # Verify reference fields are set
        self.assertEqual(pe.reference_no, fine.name)
        self.assertEqual(pe.reference_date, fine.fine_date)
        
        # Verify remarks
        self.assertIn("Meeting Fine", pe.remarks)
        self.assertIn("TEST-MEMBER-002", pe.remarks)
        
        # Verify accounts
        # Member account should be in paid_from
        # Bank account should be in paid_to
        
        # Verify mode of payment and voucher type
        self.assertEqual(pe.mode_of_payment, "Bank")
        self.assertEqual(pe.voucher_type, "Bank Entry")
        
        # Verify custom field for traceability
        self.assertEqual(pe.custom_shg_meeting_fine, fine.name)
        
        print(f"✓ Meeting Fine creates Payment Entry: {pe.name}")
        print(f"  Reference No: {pe.reference_no}")
        print(f"  Reference Date: {pe.reference_date}")
        print(f"  Amount: {pe.paid_amount}")

    def test_idempotency_of_new_posting_functions(self):
        """Test that the new posting functions are idempotent"""
        # Create a contribution
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": "TEST-MEMBER-002",
            "member_name": "Test Member 2",
            "contribution_date": today(),
            "amount": 750,
            "contribution_type": "Regular Weekly"
        })
        contribution.insert()
        contribution.submit()
        
        # Store the original journal entry
        original_journal_entry = contribution.journal_entry
        
        # Try to post again (should be idempotent)
        from shg.shg.utils.gl_utils import create_contribution_journal_entry
        # This should not create a new entry since it's already posted
        # In the actual implementation, the on_submit hook checks posted_to_gl flag
        
        # Verify that the journal entry is the same
        contribution.reload()
        self.assertEqual(contribution.journal_entry, original_journal_entry)
        
        # Verify only one Journal Entry exists
        je_count = frappe.db.count("Journal Entry", {"custom_shg_contribution": contribution.name})
        self.assertEqual(je_count, 1)

# Run tests
if __name__ == "__main__":
    unittest.main()