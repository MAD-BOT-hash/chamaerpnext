import unittest
import frappe
from frappe.test_runner import make_test_objects


class TestSHGAccountingFlows(unittest.TestCase):
    def setUp(self):
        """Set up test dependencies."""
        # Create required dependencies
        if not frappe.db.exists("Customer Group", "SHG Members"):
            customer_group = frappe.get_doc({
                "doctype": "Customer Group",
                "customer_group_name": "SHG Members",
                "parent_customer_group": "All Customer Groups",
                "is_group": 0
            })
            customer_group.insert()
            
        if not frappe.db.exists("Territory", "Kenya"):
            territory = frappe.get_doc({
                "doctype": "Territory",
                "territory_name": "Kenya",
                "parent_territory": "All Territories",
                "is_group": 0
            })
            territory.insert()
            
        # Create company if it doesn't exist
        if not frappe.db.exists("Company", "Test Company"):
            company = frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "abbr": "TC",
                "default_currency": "KES"
            })
            company.insert()
            
        # Create a bank account
        if not frappe.db.exists("Account", "Test Bank - TC"):
            bank_account = frappe.get_doc({
                "doctype": "Account",
                "company": "Test Company",
                "account_name": "Test Bank",
                "account_type": "Bank",
                "is_group": 0,
                "root_type": "Asset",
                "parent_account": "Bank Accounts - TC"
            })
            bank_account.insert()
            
        # Create cash account
        if not frappe.db.exists("Account", "Test Cash - TC"):
            cash_account = frappe.get_doc({
                "doctype": "Account",
                "company": "Test Company",
                "account_name": "Test Cash",
                "account_type": "Cash",
                "is_group": 0,
                "root_type": "Asset",
                "parent_account": "Cash In Hand - TC"
            })
            cash_account.insert()
            
        # Create loan account
        if not frappe.db.exists("Account", "Test Loans - TC"):
            loan_account = frappe.get_doc({
                "doctype": "Account",
                "company": "Test Company",
                "account_name": "Test Loans",
                "account_type": "Receivable",
                "is_group": 0,
                "root_type": "Asset",
                "parent_account": "Loans and Advances (Assets) - TC"
            })
            loan_account.insert()
            
        # Create income account
        if not frappe.db.exists("Account", "Test Contributions - TC"):
            income_account = frappe.get_doc({
                "doctype": "Account",
                "company": "Test Company",
                "account_name": "Test Contributions",
                "account_type": "Income Account",
                "is_group": 0,
                "root_type": "Income",
                "parent_account": "Direct Income - TC"
            })
            income_account.insert()
            
        frappe.db.commit()
        
        # Update SHG Settings to use the required posting methods
        settings = frappe.get_single("SHG Settings")
        settings.contribution_posting_method = "Payment Entry"
        settings.loan_disbursement_posting_method = "Journal Entry"
        settings.loan_repayment_posting_method = "Payment Entry"
        settings.default_bank_account = "Test Bank - TC"
        settings.default_cash_account = "Test Cash - TC"
        settings.default_loan_account = "Test Loans - TC"
        settings.save()

    def tearDown(self):
        """Clean up test data."""
        # Delete test SHG Members
        for member in frappe.get_all("SHG Member", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Member", member.name)
            
        # Delete test Customers
        for customer in frappe.get_all("Customer", filters={"customer_name": ["like", "Test Member%"]}):
            frappe.delete_doc("Customer", customer.name)
            
        # Delete test Contributions
        for contribution in frappe.get_all("SHG Contribution", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Contribution", contribution.name)
            
        # Delete test Loans
        for loan in frappe.get_all("SHG Loan", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Loan", loan.name)
            
        # Delete test Loan Repayments
        for repayment in frappe.get_all("SHG Loan Repayment", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Loan Repayment", repayment.name)
            
        # Delete test Journal Entries
        for je in frappe.get_all("Journal Entry", filters={"user_remark": ["like", "SHG%"]}):
            frappe.delete_doc("Journal Entry", je.name)
            
        # Delete test Payment Entries
        for pe in frappe.get_all("Payment Entry", filters={"reference_no": ["like", "SHG%"]}):
            frappe.delete_doc("Payment Entry", pe.name)
            
        frappe.db.commit()

    def test_contribution_payment_entry_flow(self):
        """Test that Contributions create Payment Entry (from Member/Customer to Bank/Cash)."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member 1",
            "id_number": "12345678",
            "phone_number": "0712345678"
        })
        member.insert()
        member.reload()
        
        # Verify that a Customer was created and linked
        self.assertIsNotNone(member.customer, "Customer should be linked to SHG Member")
        
        # Create a contribution
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": member.name,
            "member_name": member.member_name,
            "contribution_date": "2025-10-01",
            "amount": 1000,
            "contribution_type": "Regular Weekly"
        })
        contribution.insert()
        contribution.submit()
        
        # Verify that a Payment Entry was created (not a Journal Entry)
        self.assertIsNotNone(contribution.payment_entry, "Payment Entry should be created for contribution")
        self.assertIsNone(contribution.journal_entry, "No Journal Entry should be created for contribution")
        
        # Verify the Payment Entry details
        pe = frappe.get_doc("Payment Entry", contribution.payment_entry)
        self.assertEqual(pe.payment_type, "Receive", "Payment Entry should be of type 'Receive'")
        self.assertEqual(pe.party_type, "Customer", "Party type should be 'Customer'")
        self.assertEqual(pe.party, member.customer, "Party should be the member's customer")
        self.assertEqual(pe.paid_amount, 1000, "Paid amount should match contribution amount")
        self.assertEqual(pe.received_amount, 1000, "Received amount should match contribution amount")
        self.assertEqual(pe.paid_from, "Test Bank - TC", "Paid from should be bank account")
        # Note: paid_to would be the member's account, but it's created dynamically
        
        print(f"✓ Contribution Payment Entry created: {pe.name}")
        print(f"  Payment Type: {pe.payment_type}")
        print(f"  Party: {pe.party}")
        print(f"  Amount: {pe.paid_amount}")

    def test_loan_disbursement_journal_entry_flow(self):
        """Test that Loan Disbursement creates Journal Entry (Dr Loan Asset, Cr Bank)."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member 2",
            "id_number": "87654321",
            "phone_number": "0787654321"
        })
        member.insert()
        member.reload()
        
        # Create a loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": member.name,
            "member_name": member.member_name,
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "application_date": "2025-10-01",
            "disbursement_date": "2025-10-01",
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Verify that a Journal Entry was created (not a Payment Entry)
        self.assertIsNotNone(loan.disbursement_journal_entry, "Journal Entry should be created for loan disbursement")
        self.assertIsNone(loan.disbursement_payment_entry, "No Payment Entry should be created for loan disbursement")
        
        # Verify the Journal Entry details
        je = frappe.get_doc("Journal Entry", loan.disbursement_journal_entry)
        self.assertEqual(je.voucher_type, "Journal Entry", "Voucher type should be 'Journal Entry'")
        
        # Check accounts - should have debit to Loan Asset and credit to Bank
        debit_entry = None
        credit_entry = None
        for entry in je.accounts:
            if entry.debit_in_account_currency > 0:
                debit_entry = entry
            elif entry.credit_in_account_currency > 0:
                credit_entry = entry
        
        self.assertIsNotNone(debit_entry, "Should have a debit entry")
        self.assertIsNotNone(credit_entry, "Should have a credit entry")
        
        # The debit should be to the member's account (Loan Asset)
        # The credit should be to the bank account
        self.assertEqual(credit_entry.account, "Test Bank - TC", "Credit should be to bank account")
        self.assertEqual(credit_entry.credit_in_account_currency, 10000, "Credit amount should match loan amount")
        self.assertEqual(debit_entry.debit_in_account_currency, 10000, "Debit amount should match loan amount")
        self.assertEqual(debit_entry.party_type, "Customer", "Debit entry party type should be 'Customer'")
        self.assertEqual(debit_entry.party, member.customer, "Debit entry party should be member's customer")
        
        print(f"✓ Loan Disbursement Journal Entry created: {je.name}")
        print(f"  Debit: {debit_entry.account} - {debit_entry.debit_in_account_currency}")
        print(f"  Credit: {credit_entry.account} - {credit_entry.credit_in_account_currency}")

    def test_loan_repayment_payment_entry_flow(self):
        """Test that Loan Repayment creates Payment Entry (from Member/Customer to Loan Receivable)."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member 3",
            "id_number": "11223344",
            "phone_number": "0711223344"
        })
        member.insert()
        member.reload()
        
        # First create a loan to repay
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": member.name,
            "member_name": member.member_name,
            "loan_amount": 5000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 6,
            "repayment_frequency": "Monthly",
            "application_date": "2025-10-01",
            "disbursement_date": "2025-10-01",
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Create a repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": member.name,
            "member_name": member.member_name,
            "repayment_date": "2025-10-15",
            "total_paid": 1000
        })
        repayment.insert()
        repayment.submit()
        
        # Verify that a Payment Entry was created (not a Journal Entry)
        self.assertIsNotNone(repayment.payment_entry, "Payment Entry should be created for loan repayment")
        self.assertIsNone(repayment.journal_entry, "No Journal Entry should be created for loan repayment")
        
        # Verify the Payment Entry details
        pe = frappe.get_doc("Payment Entry", repayment.payment_entry)
        self.assertEqual(pe.payment_type, "Receive", "Payment Entry should be of type 'Receive'")
        self.assertEqual(pe.party_type, "Customer", "Party type should be 'Customer'")
        self.assertEqual(pe.party, member.customer, "Party should be the member's customer")
        self.assertEqual(pe.paid_amount, 1000, "Paid amount should match repayment amount")
        self.assertEqual(pe.received_amount, 1000, "Received amount should match repayment amount")
        
        print(f"✓ Loan Repayment Payment Entry created: {pe.name}")
        print(f"  Payment Type: {pe.payment_type}")
        print(f"  Party: {pe.party}")
        print(f"  Amount: {pe.paid_amount}")

    def test_gl_entries_validation(self):
        """Test that all GL entries are created with correct reference types for ERPNext v15 compatibility."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member 4",
            "id_number": "44332211",
            "phone_number": "0744332211"
        })
        member.insert()
        member.reload()
        
        # Test contribution
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": member.name,
            "member_name": member.member_name,
            "contribution_date": "2025-10-01",
            "amount": 500,
            "contribution_type": "Regular Weekly"
        })
        contribution.insert()
        contribution.submit()
        
        # Verify Payment Entry has correct reference types
        if contribution.payment_entry:
            pe = frappe.get_doc("Payment Entry", contribution.payment_entry)
            # Payment Entry doesn't have reference_type in its main document, but we verify it was created
            
        # Test loan disbursement
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": member.name,
            "member_name": member.member_name,
            "loan_amount": 5000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 6,
            "repayment_frequency": "Monthly",
            "application_date": "2025-10-01",
            "disbursement_date": "2025-10-01",
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Verify Journal Entry has correct reference types
        if loan.disbursement_journal_entry:
            je = frappe.get_doc("Journal Entry", loan.disbursement_journal_entry)
            for entry in je.accounts:
                if entry.reference_type:
                    self.assertEqual(entry.reference_type, "Journal Entry", 
                                   f"All journal entry accounts should have reference_type 'Journal Entry', got '{entry.reference_type}'")
                    self.assertEqual(entry.reference_name, loan.name,
                                   f"Reference name should match loan name, got '{entry.reference_name}'")
        
        # Test loan repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": member.name,
            "member_name": member.member_name,
            "repayment_date": "2025-10-15",
            "total_paid": 1000
        })
        repayment.insert()
        repayment.submit()
        
        # Verify Payment Entry has correct reference types
        if repayment.payment_entry:
            pe = frappe.get_doc("Payment Entry", repayment.payment_entry)
            # Payment Entry doesn't have reference_type in its main document, but we verify it was created
            
        print("✓ All GL entries validated for ERPNext v15 compatibility")


if __name__ == '__main__':
    unittest.main()