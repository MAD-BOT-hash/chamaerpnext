import frappe
import unittest
from frappe.utils import today, flt

class TestNewPostingFlow(unittest.TestCase):
    """Test the new posting flow using Journal Entry or Payment Entry as canonical posting mechanism"""
    
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
        if not frappe.db.exists("SHG Member", "TEST-MEMBER-001"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "Test Member",
                "gender": "Male",
                "date_of_birth": "1990-01-01",
                "phone_number": "+254700000000",
                "email": "test@example.com",
                "address": "Test Address",
                "membership_status": "Active"
            })
            member.insert()
            
        # Create a test customer for the member
        if not frappe.db.exists("Customer", "Test Member"):
            customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": "Test Member",
                "customer_type": "Individual",
                "customer_group": "All Customer Groups",
                "territory": "All Territories"
            })
            customer.insert()
            
        # Link customer to member
        member = frappe.get_doc("SHG Member", "TEST-MEMBER-001")
        member.customer = "Test Member"
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
        settings.save()
    
    def test_contribution_posts_to_journal_entry(self):
        """Test that SHG Contribution creates and submits a Journal Entry and the SHG doc gets posted_to_gl=1"""
        # Create a contribution
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
            "contribution_date": today(),
            "amount": 1000,
            "contribution_type": "Regular Weekly"
        })
        contribution.insert()
        contribution.submit()
        
        # Verify that the contribution was posted to GL
        self.assertEqual(contribution.posted_to_gl, 1)
        self.assertIsNotNone(contribution.journal_entry)
        self.assertIsNone(contribution.payment_entry)  # Should use Journal Entry by default
        
        # Verify that the Journal Entry exists and is submitted
        self.assertTrue(frappe.db.exists("Journal Entry", contribution.journal_entry))
        je = frappe.get_doc("Journal Entry", contribution.journal_entry)
        self.assertEqual(je.docstatus, 1)
        
        # Verify that the Journal Entry has correct accounts and party details
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
        self.assertAlmostEqual(debit_entry.debit_in_account_currency, 1000, places=2)
        self.assertAlmostEqual(credit_entry.credit_in_account_currency, 1000, places=2)
        
        # Verify party details for credit entry (member account)
        self.assertEqual(credit_entry.party_type, "Customer")
        self.assertEqual(credit_entry.party, "Test Member")
        
        # Verify reference types are valid
        self.assertEqual(debit_entry.reference_type, "Journal Entry")
        self.assertEqual(credit_entry.reference_type, "Journal Entry")
        self.assertEqual(debit_entry.reference_name, contribution.name)
        self.assertEqual(credit_entry.reference_name, contribution.name)
    
    def test_contribution_posts_to_payment_entry(self):
        """Test that SHG Contribution creates and submits a Payment Entry when configured to do so"""
        # Update settings to use Payment Entry for contributions
        settings = frappe.get_single("SHG Settings")
        settings.contribution_posting_method = "Payment Entry"
        settings.save()
        
        # Create a contribution
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
            "contribution_date": today(),
            "amount": 1000,
            "contribution_type": "Regular Weekly"
        })
        contribution.insert()
        contribution.submit()
        
        # Verify that the contribution was posted to GL
        self.assertEqual(contribution.posted_to_gl, 1)
        self.assertIsNotNone(contribution.payment_entry)
        self.assertIsNone(contribution.journal_entry)  # Should use Payment Entry
        
        # Verify that the Payment Entry exists and is submitted
        self.assertTrue(frappe.db.exists("SHG Payment Entry", contribution.payment_entry))
        pe = frappe.get_doc("Payment Entry", contribution.payment_entry)
        self.assertEqual(pe.docstatus, 1)
        
        # Verify that the Payment Entry has correct details
        self.assertEqual(pe.payment_type, "Receive")
        self.assertEqual(pe.party_type, "Customer")
        self.assertEqual(pe.party, "Test Member")
        self.assertAlmostEqual(pe.paid_amount, 1000, places=2)
        self.assertAlmostEqual(pe.received_amount, 1000, places=2)
        
        # Reset settings
        settings.contribution_posting_method = "Journal Entry"
        settings.save()
    
    def test_loan_disbursement_posts_to_journal_entry(self):
        """Test that SHG Loan disbursement creates and submits a Journal Entry"""
        # Create a loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
            "loan_amount": 10000,
            "interest_rate": 12,
            "loan_period_months": 12,
            "disbursement_date": today(),
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Verify that the loan was posted to GL
        self.assertEqual(loan.posted_to_gl, 1)
        self.assertIsNotNone(loan.disbursement_journal_entry)
        self.assertIsNone(loan.disbursement_payment_entry)  # Should use Journal Entry by default
        
        # Verify that the Journal Entry exists and is submitted
        self.assertTrue(frappe.db.exists("Journal Entry", loan.disbursement_journal_entry))
        je = frappe.get_doc("Journal Entry", loan.disbursement_journal_entry)
        self.assertEqual(je.docstatus, 1)
        
        # Verify that the Journal Entry has correct accounts and party details
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
        self.assertAlmostEqual(debit_entry.debit_in_account_currency, 10000, places=2)
        self.assertAlmostEqual(credit_entry.credit_in_account_currency, 10000, places=2)
        
        # Verify party details for debit entry (member account)
        self.assertEqual(debit_entry.party_type, "Customer")
        self.assertEqual(debit_entry.party, "Test Member")
        
        # Verify reference types are valid
        self.assertEqual(debit_entry.reference_type, "Journal Entry")
        self.assertEqual(credit_entry.reference_type, "Journal Entry")
        self.assertEqual(debit_entry.reference_name, loan.name)
        self.assertEqual(credit_entry.reference_name, loan.name)
    
    def test_loan_repayment_posts_to_journal_entry(self):
        """Test that SHG Loan Repayment creates and submits a Journal Entry"""
        # Create a loan first
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
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
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
            "repayment_date": today(),
            "total_paid": 1000,
            "principal_amount": 900,
            "interest_amount": 100
        })
        repayment.insert()
        repayment.submit()
        
        # Verify that the repayment was posted to GL
        self.assertEqual(repayment.posted_to_gl, 1)
        self.assertIsNotNone(repayment.journal_entry)
        self.assertIsNone(repayment.payment_entry)  # Should use Journal Entry by default
        
        # Verify that the Journal Entry exists and is submitted
        self.assertTrue(frappe.db.exists("Journal Entry", repayment.journal_entry))
        je = frappe.get_doc("Journal Entry", repayment.journal_entry)
        self.assertEqual(je.docstatus, 1)
        
        # Verify that the Journal Entry has correct accounts
        # Should have at least 3 entries: bank debit, principal credit, interest credit
        self.assertGreaterEqual(len(je.accounts), 3)
        
        # Find entries
        total_debit = sum(entry.debit_in_account_currency for entry in je.accounts)
        total_credit = sum(entry.credit_in_account_currency for entry in je.accounts)
        
        # Verify amounts balance
        self.assertAlmostEqual(total_debit, total_credit, places=2)
        self.assertAlmostEqual(total_debit, 1000, places=2)
        
        # Verify party details for credit entries
        credit_entries_with_party = [entry for entry in je.accounts if entry.credit_in_account_currency > 0 and entry.party_type and entry.party]
        self.assertGreaterEqual(len(credit_entries_with_party), 1)
        
        for entry in credit_entries_with_party:
            self.assertEqual(entry.party_type, "Customer")
            self.assertEqual(entry.party, "Test Member")
        
        # Verify reference types are valid
        for entry in je.accounts:
            if entry.debit_in_account_currency > 0 or entry.credit_in_account_currency > 0:
                self.assertEqual(entry.reference_type, "Journal Entry")
                self.assertEqual(entry.reference_name, repayment.name)
    
    def test_meeting_fine_posts_to_journal_entry(self):
        """Test that SHG Meeting Fine creates and submits a Journal Entry"""
        # Create a meeting fine
        fine = frappe.get_doc({
            "doctype": "SHG Meeting Fine",
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
            "fine_date": today(),
            "fine_amount": 200,
            "fine_reason": "Late Arrival",
            "status": "Paid"
        })
        fine.insert()
        fine.submit()
        
        # Verify that the fine was posted to GL
        self.assertEqual(fine.posted_to_gl, 1)
        self.assertIsNotNone(fine.journal_entry)
        self.assertIsNone(fine.payment_entry)  # Should use Journal Entry by default
        
        # Verify that the Journal Entry exists and is submitted
        self.assertTrue(frappe.db.exists("Journal Entry", fine.journal_entry))
        je = frappe.get_doc("Journal Entry", fine.journal_entry)
        self.assertEqual(je.docstatus, 1)
        
        # Verify that the Journal Entry has correct accounts and party details
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
        self.assertAlmostEqual(debit_entry.debit_in_account_currency, 200, places=2)
        self.assertAlmostEqual(credit_entry.credit_in_account_currency, 200, places=2)
        
        # Verify party details for debit entry (member account)
        self.assertEqual(debit_entry.party_type, "Customer")
        self.assertEqual(debit_entry.party, "Test Member")
        
        # Verify reference types are valid
        self.assertEqual(debit_entry.reference_type, "Journal Entry")
        self.assertEqual(credit_entry.reference_type, "Journal Entry")
        self.assertEqual(debit_entry.reference_name, fine.name)
        self.assertEqual(credit_entry.reference_name, fine.name)
    
    def test_idempotency_of_posting(self):
        """Test that posting is idempotent - calling post_to_ledger multiple times doesn't create duplicates"""
        # Create a contribution
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
            "contribution_date": today(),
            "amount": 1000,
            "contribution_type": "Regular Weekly"
        })
        contribution.insert()
        contribution.submit()
        
        # Store the original journal entry
        original_journal_entry = contribution.journal_entry
        
        # Try to post again (should be idempotent)
        contribution.post_to_ledger()
        
        # Verify that the journal entry is the same
        self.assertEqual(contribution.journal_entry, original_journal_entry)
        
        # Verify only one Journal Entry exists
        je_count = frappe.db.count("Journal Entry", {"reference_name": contribution.name})
        self.assertEqual(je_count, 1)

# Run tests
if __name__ == "__main__":
    unittest.main()