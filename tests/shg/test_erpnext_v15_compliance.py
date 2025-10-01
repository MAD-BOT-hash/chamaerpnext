import unittest
import frappe


class TestERPNextV15Compliance(unittest.TestCase):
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
            
        # Create accounts
        self.create_test_accounts()
            
        frappe.db.commit()
        
        # Update SHG Settings to use the required posting methods
        settings = frappe.get_single("SHG Settings")
        settings.contribution_posting_method = "Journal Entry"
        settings.loan_disbursement_posting_method = "Journal Entry"
        settings.loan_repayment_posting_method = "Journal Entry"
        settings.default_bank_account = "Test Bank - TC"
        settings.default_cash_account = "Test Cash - TC"
        settings.default_loan_account = "Test Loans - TC"
        settings.save()

    def create_test_accounts(self):
        """Create test accounts."""
        company = "Test Company"
        abbr = "TC"
        
        # Create parent accounts if they don't exist
        if not frappe.db.exists("Account", f"Application of Funds (Assets) - {abbr}"):
            parent_asset = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Application of Funds (Assets)",
                "is_group": 1,
                "root_type": "Asset",
                "report_type": "Balance Sheet"
            })
            parent_asset.insert()
            
        if not frappe.db.exists("Account", f"Current Assets - {abbr}"):
            current_assets = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Current Assets",
                "is_group": 1,
                "root_type": "Asset",
                "report_type": "Balance Sheet",
                "parent_account": f"Application of Funds (Assets) - {abbr}"
            })
            current_assets.insert()
            
        if not frappe.db.exists("Account", f"Bank Accounts - {abbr}"):
            bank_parent = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Bank Accounts",
                "is_group": 1,
                "root_type": "Asset",
                "report_type": "Balance Sheet",
                "parent_account": f"Current Assets - {abbr}"
            })
            bank_parent.insert()
            
        if not frappe.db.exists("Account", f"Cash In Hand - {abbr}"):
            cash_parent = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Cash In Hand",
                "is_group": 1,
                "root_type": "Asset",
                "report_type": "Balance Sheet",
                "parent_account": f"Current Assets - {abbr}"
            })
            cash_parent.insert()
            
        if not frappe.db.exists("Account", f"Income - {abbr}"):
            income_parent = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Income",
                "is_group": 1,
                "root_type": "Income",
                "report_type": "Profit and Loss"
            })
            income_parent.insert()
            
        if not frappe.db.exists("Account", f"Direct Income - {abbr}"):
            direct_income = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Direct Income",
                "is_group": 1,
                "root_type": "Income",
                "report_type": "Profit and Loss",
                "parent_account": f"Income - {abbr}"
            })
            direct_income.insert()
            
        # Create specific accounts
        if not frappe.db.exists("Account", f"Test Bank - {abbr}"):
            bank_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Test Bank",
                "account_type": "Bank",
                "is_group": 0,
                "root_type": "Asset",
                "parent_account": f"Bank Accounts - {abbr}"
            })
            bank_account.insert()
            
        if not frappe.db.exists("Account", f"Test Cash - {abbr}"):
            cash_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Test Cash",
                "account_type": "Cash",
                "is_group": 0,
                "root_type": "Asset",
                "parent_account": f"Cash In Hand - {abbr}"
            })
            cash_account.insert()
            
        if not frappe.db.exists("Account", f"Test Loans - {abbr}"):
            loan_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Test Loans",
                "account_type": "Receivable",
                "is_group": 0,
                "root_type": "Asset",
                "parent_account": f"Current Assets - {abbr}"
            })
            loan_account.insert()
            
        if not frappe.db.exists("Account", f"Test Contributions - {abbr}"):
            income_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Test Contributions",
                "account_type": "Income Account",
                "is_group": 0,
                "root_type": "Income",
                "parent_account": f"Direct Income - {abbr}"
            })
            income_account.insert()

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
            
        frappe.db.commit()

    def test_contribution_journal_entry_flow(self):
        """Test that Contributions create Journal Entry (Dr Bank/Cash, Cr SHG Contributions Income)."""
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
        
        # Verify that a Journal Entry was created
        self.assertIsNotNone(contribution.journal_entry, "Journal Entry should be created for contribution")
        self.assertIsNone(contribution.payment_entry, "No Payment Entry should be created for contribution")
        
        # Verify the Journal Entry details
        je = frappe.get_doc("Journal Entry", contribution.journal_entry)
        self.assertEqual(je.voucher_type, "Journal Entry", "Voucher type should be 'Journal Entry'")
        
        # Check accounts - should have debit to Bank/Cash and credit to Contribution Income
        debit_entry = None
        credit_entry = None
        for entry in je.accounts:
            if entry.debit_in_account_currency > 0:
                debit_entry = entry
            elif entry.credit_in_account_currency > 0:
                credit_entry = entry
        
        self.assertIsNotNone(debit_entry, "Should have a debit entry")
        self.assertIsNotNone(credit_entry, "Should have a credit entry")
        
        # The debit should be to bank/cash account and credit to contribution income
        self.assertIn("Test Bank", debit_entry.account, "Debit should be to bank account")
        self.assertEqual(debit_entry.debit_in_account_currency, 1000, "Debit amount should match contribution amount")
        self.assertIn("Test Contributions", credit_entry.account, "Credit should be to contribution income account")
        self.assertEqual(credit_entry.credit_in_account_currency, 1000, "Credit amount should match contribution amount")
        self.assertEqual(credit_entry.party_type, "Customer", "Credit entry party type should be 'Customer'")
        self.assertEqual(credit_entry.party, member.customer, "Credit entry party should be member's customer")
        
        # Verify reference types for ERPNext v15 compatibility
        for entry in je.accounts:
            if entry.reference_type:
                self.assertEqual(entry.reference_type, "Journal Entry", 
                               f"All journal entry accounts should have reference_type 'Journal Entry', got '{entry.reference_type}'")
                self.assertEqual(entry.reference_name, contribution.name,
                               f"Reference name should match contribution name, got '{entry.reference_name}'")
        
        print(f"✓ Contribution Journal Entry created: {je.name}")
        print(f"  Debit: {debit_entry.account} - KES {debit_entry.debit_in_account_currency:,.2f}")
        print(f"  Credit: {credit_entry.account} - KES {credit_entry.credit_in_account_currency:,.2f}")

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
        
        # Verify that a Journal Entry was created
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
        
        # The debit should be to the loan asset account and credit to bank account
        self.assertIn("Test Loans", debit_entry.account, "Debit should be to loan asset account")
        self.assertEqual(debit_entry.debit_in_account_currency, 10000, "Debit amount should match loan amount")
        self.assertIn("Test Bank", credit_entry.account, "Credit should be to bank account")
        self.assertEqual(credit_entry.credit_in_account_currency, 10000, "Credit amount should match loan amount")
        
        # Verify reference types for ERPNext v15 compatibility
        for entry in je.accounts:
            if entry.reference_type:
                self.assertEqual(entry.reference_type, "Journal Entry", 
                               f"All journal entry accounts should have reference_type 'Journal Entry', got '{entry.reference_type}'")
                self.assertEqual(entry.reference_name, loan.name,
                               f"Reference name should match loan name, got '{entry.reference_name}'")
        
        print(f"✓ Loan Disbursement Journal Entry created: {je.name}")
        print(f"  Debit: {debit_entry.account} - KES {debit_entry.debit_in_account_currency:,.2f}")
        print(f"  Credit: {credit_entry.account} - KES {credit_entry.credit_in_account_currency:,.2f}")

    def test_loan_repayment_journal_entry_flow(self):
        """Test that Loan Repayment creates Journal Entry (Dr Bank/Cash, Cr Loan Receivable + Interest/Penalty)."""
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
            "total_paid": 1000,
            "principal_amount": 800,
            "interest_amount": 200
        })
        repayment.insert()
        repayment.submit()
        
        # Verify that a Journal Entry was created
        self.assertIsNotNone(repayment.journal_entry, "Journal Entry should be created for loan repayment")
        self.assertIsNone(repayment.payment_entry, "No Payment Entry should be created for loan repayment")
        
        # Verify the Journal Entry details
        je = frappe.get_doc("Journal Entry", repayment.journal_entry)
        self.assertEqual(je.voucher_type, "Journal Entry", "Voucher type should be 'Journal Entry'")
        
        # Check accounts
        debit_total = sum(entry.debit_in_account_currency for entry in je.accounts)
        credit_total = sum(entry.credit_in_account_currency for entry in je.accounts)
        
        self.assertEqual(debit_total, 1000, "Total debit should match repayment amount")
        self.assertEqual(credit_total, 1000, "Total credit should match repayment amount")
        
        # Find specific entries
        debit_entry = None
        principal_credit = None
        interest_credit = None
        
        for entry in je.accounts:
            if entry.debit_in_account_currency > 0:
                debit_entry = entry
            elif entry.account_type == "Receivable" and entry.credit_in_account_currency > 0:
                principal_credit = entry
            elif "Interest" in entry.account and entry.credit_in_account_currency > 0:
                interest_credit = entry
        
        # Verify debit is from Bank/Cash
        self.assertIsNotNone(debit_entry, "Should have a debit entry")
        self.assertIn("Test Bank", debit_entry.account, "Debit should be from bank account")
        self.assertEqual(debit_entry.debit_in_account_currency, 1000, "Debit amount should match total repayment")
        
        # Verify credit to Loan Receivable
        self.assertIsNotNone(principal_credit, "Should have principal credit entry")
        self.assertIn("Test Loans", principal_credit.account, "Principal credit should be to loan account")
        self.assertEqual(principal_credit.credit_in_account_currency, 800, "Principal credit should match principal amount")
        
        # Verify credit to Interest Income
        self.assertIsNotNone(interest_credit, "Should have interest credit entry")
        self.assertIn("Interest", interest_credit.account, "Interest credit should be to interest account")
        self.assertEqual(interest_credit.credit_in_account_currency, 200, "Interest credit should match interest amount")
        
        # Verify reference types for ERPNext v15 compatibility
        for entry in je.accounts:
            if entry.reference_type:
                self.assertEqual(entry.reference_type, "Journal Entry", 
                               f"All journal entry accounts should have reference_type 'Journal Entry', got '{entry.reference_type}'")
                self.assertEqual(entry.reference_name, repayment.name,
                               f"Reference name should match repayment name, got '{entry.reference_name}'")
        
        print(f"✓ Loan Repayment Journal Entry created: {je.name}")
        print(f"  Debit: {debit_entry.account} - KES {debit_entry.debit_in_account_currency:,.2f}")
        print(f"  Principal Credit: {principal_credit.account} - KES {principal_credit.credit_in_account_currency:,.2f}")
        print(f"  Interest Credit: {interest_credit.account} - KES {interest_credit.credit_in_account_currency:,.2f}")

    def test_erpnext_v15_reference_type_compatibility(self):
        """Test that all created documents have valid reference types for ERPNext v15."""
        # Valid reference types for ERPNext v15
        valid_reference_types = [
            "", "Sales Invoice", "Purchase Invoice", "Journal Entry", "Sales Order", 
            "Purchase Order", "Expense Claim", "Asset", "Loan", "Payroll Entry", 
            "Employee Advance", "Exchange Rate Revaluation", "Invoice Discounting", 
            "Fees", "Full and Final Statement", "Payment Entry", "Loan Interest Accrual"
        ]
        
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
        
        # Verify Journal Entry reference types
        if contribution.journal_entry:
            je = frappe.get_doc("Journal Entry", contribution.journal_entry)
            for entry in je.accounts:
                if entry.reference_type:
                    self.assertIn(entry.reference_type, valid_reference_types,
                                f"Reference type '{entry.reference_type}' should be valid for ERPNext v15")
        
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
        
        # Verify Journal Entry reference types
        if loan.disbursement_journal_entry:
            je = frappe.get_doc("Journal Entry", loan.disbursement_journal_entry)
            for entry in je.accounts:
                if entry.reference_type:
                    self.assertIn(entry.reference_type, valid_reference_types,
                                f"Reference type '{entry.reference_type}' should be valid for ERPNext v15")
        
        # Test loan repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": member.name,
            "member_name": member.member_name,
            "repayment_date": "2025-10-15",
            "total_paid": 1000,
            "principal_amount": 800,
            "interest_amount": 200
        })
        repayment.insert()
        repayment.submit()
        
        # Verify Journal Entry reference types
        if repayment.journal_entry:
            je = frappe.get_doc("Journal Entry", repayment.journal_entry)
            for entry in je.accounts:
                if entry.reference_type:
                    self.assertIn(entry.reference_type, valid_reference_types,
                                f"Reference type '{entry.reference_type}' should be valid for ERPNext v15")
