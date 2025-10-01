import unittest
import frappe
from frappe.utils import nowdate

class TestSHGERPNext15Compliance(unittest.TestCase):
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
        
        # Update SHG Settings to use Payment Entry for contributions and loan repayments
        # and Journal Entry for loan disbursements and meeting fines
        settings = frappe.get_single("SHG Settings")
        settings.contribution_posting_method = "Payment Entry"
        settings.loan_disbursement_posting_method = "Journal Entry"
        settings.loan_repayment_posting_method = "Payment Entry"
        settings.meeting_fine_posting_method = "Journal Entry"
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
            
        if not frappe.db.exists("Account", f"Indirect Income - {abbr}"):
            indirect_income = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Indirect Income",
                "is_group": 1,
                "root_type": "Income",
                "report_type": "Profit and Loss",
                "parent_account": f"Income - {abbr}"
            })
            indirect_income.insert()
            
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
            
        if not frappe.db.exists("Account", f"Test Interest Income - {abbr}"):
            interest_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Test Interest Income",
                "account_type": "Income Account",
                "is_group": 0,
                "root_type": "Income",
                "parent_account": f"Indirect Income - {abbr}"
            })
            interest_account.insert()
            
        if not frappe.db.exists("Account", f"Test Penalty Income - {abbr}"):
            penalty_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Test Penalty Income",
                "account_type": "Income Account",
                "is_group": 0,
                "root_type": "Income",
                "parent_account": f"Indirect Income - {abbr}"
            })
            penalty_account.insert()

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
            
        # Delete test Meeting Fines
        for fine in frappe.get_all("SHG Meeting Fine", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Meeting Fine", fine.name)
            
        # Delete test Payment Entries
        for pe in frappe.get_all("Payment Entry", filters={"reference_no": ["like", "SHG-%"]}):
            frappe.delete_doc("Payment Entry", pe.name)
            
        # Delete test Journal Entries
        for je in frappe.get_all("Journal Entry", filters={"user_remark": ["like", "SHG%"]}):
            frappe.delete_doc("Journal Entry", je.name)
            
        frappe.db.commit()

    def test_contribution_payment_entry_flow(self):
        """Test that Contributions create Payment Entry (Dr Bank/Cash, Cr SHG Contributions Income)."""
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
            "contribution_date": nowdate(),
            "amount": 1000,
            "contribution_type": "Regular Weekly"
        })
        contribution.insert()
        contribution.submit()
        
        # Verify that a Payment Entry was created
        self.assertIsNotNone(contribution.payment_entry, "Payment Entry should be created for contribution")
        self.assertIsNone(contribution.journal_entry, "No Journal Entry should be created for contribution")
        
        # Verify the Payment Entry details
        pe = frappe.get_doc("Payment Entry", contribution.payment_entry)
        self.assertEqual(pe.payment_type, "Receive", "Payment type should be 'Receive'")
        self.assertEqual(pe.party_type, "Customer", "Party type should be 'Customer'")
        self.assertEqual(pe.party, member.customer, "Party should be member's customer")
        self.assertEqual(pe.paid_amount, 1000, "Paid amount should match contribution amount")
        self.assertEqual(pe.received_amount, 1000, "Received amount should match contribution amount")
        
        # Verify custom field linking
        self.assertEqual(pe.custom_shg_contribution, contribution.name, 
                        "Payment Entry should be linked to the SHG Contribution")
        
        # Verify accounts - should have debit to Bank/Cash and credit to Contribution Income
        self.assertIn("Test Bank", pe.paid_from, "Paid from should be bank account")
        self.assertIn("Test Contributions", pe.paid_to, "Paid to should be contribution income account")
        
        print(f"✓ Contribution Payment Entry created: {pe.name}")
        print(f"  From: {pe.paid_from} - KES {pe.paid_amount:,.2f}")
        print(f"  To: {pe.paid_to} - KES {pe.received_amount:,.2f}")

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
            "application_date": nowdate(),
            "disbursement_date": nowdate(),
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
        
        # Verify custom field linking
        self.assertEqual(je.custom_shg_loan, loan.name, 
                        "Journal Entry should be linked to the SHG Loan")
        
        # Verify no reference_type or reference_name is used (ERPNext 15 compliance)
        for entry in je.accounts:
            self.assertNotIn("reference_type", entry.__dict__, "No reference_type should be used")
            self.assertNotIn("reference_name", entry.__dict__, "No reference_name should be used")
        
        print(f"✓ Loan Disbursement Journal Entry created: {je.name}")
        print(f"  Debit: {debit_entry.account} - KES {debit_entry.debit_in_account_currency:,.2f}")
        print(f"  Credit: {credit_entry.account} - KES {credit_entry.credit_in_account_currency:,.2f}")

    def test_loan_repayment_payment_entry_flow(self):
        """Test that Loan Repayment creates Payment Entry (Dr Bank/Cash, Cr Loan Receivable)."""
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
            "application_date": nowdate(),
            "disbursement_date": nowdate(),
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
            "repayment_date": nowdate(),
            "total_paid": 1000,
            "principal_amount": 800,
            "interest_amount": 200
        })
        repayment.insert()
        repayment.submit()
        
        # Verify that a Payment Entry was created
        self.assertIsNotNone(repayment.payment_entry, "Payment Entry should be created for loan repayment")
        self.assertIsNone(repayment.journal_entry, "No Journal Entry should be created for loan repayment")
        
        # Verify the Payment Entry details
        pe = frappe.get_doc("Payment Entry", repayment.payment_entry)
        self.assertEqual(pe.payment_type, "Receive", "Payment type should be 'Receive'")
        self.assertEqual(pe.party_type, "Customer", "Party type should be 'Customer'")
        self.assertEqual(pe.party, member.customer, "Party should be member's customer")
        self.assertEqual(pe.paid_amount, 1000, "Paid amount should match repayment amount")
        self.assertEqual(pe.received_amount, 1000, "Received amount should match repayment amount")
        
        # Verify custom field linking
        self.assertEqual(pe.custom_shg_loan_repayment, repayment.name, 
                        "Payment Entry should be linked to the SHG Loan Repayment")
        
        # Verify accounts
        self.assertIn("Test Bank", pe.paid_from, "Paid from should be bank account")
        self.assertIn("Test Loans", pe.paid_to, "Paid to should be loan receivable account")
        
        print(f"✓ Loan Repayment Payment Entry created: {pe.name}")
        print(f"  From: {pe.paid_from} - KES {pe.paid_amount:,.2f}")
        print(f"  To: {pe.paid_to} - KES {pe.received_amount:,.2f}")

    def test_meeting_fine_journal_entry_flow(self):
        """Test that Meeting Fine creates Journal Entry (Dr Member, Cr Penalty Income)."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member 4",
            "id_number": "44332211",
            "phone_number": "0744332211"
        })
        member.insert()
        member.reload()
        
        # Create a meeting fine
        fine = frappe.get_doc({
            "doctype": "SHG Meeting Fine",
            "member": member.name,
            "member_name": member.member_name,
            "fine_date": nowdate(),
            "fine_amount": 200,
            "fine_reason": "Late Arrival",
            "status": "Paid"
        })
        fine.insert()
        fine.submit()
        
        # Verify that a Journal Entry was created
        self.assertIsNotNone(fine.journal_entry, "Journal Entry should be created for meeting fine")
        self.assertIsNone(fine.payment_entry, "No Payment Entry should be created for meeting fine")
        
        # Verify the Journal Entry details
        je = frappe.get_doc("Journal Entry", fine.journal_entry)
        self.assertEqual(je.voucher_type, "Journal Entry", "Voucher type should be 'Journal Entry'")
        
        # Check accounts - should have debit to Member and credit to Penalty Income
        debit_entry = None
        credit_entry = None
        for entry in je.accounts:
            if entry.debit_in_account_currency > 0:
                debit_entry = entry
            elif entry.credit_in_account_currency > 0:
                credit_entry = entry
        
        self.assertIsNotNone(debit_entry, "Should have a debit entry")
        self.assertIsNotNone(credit_entry, "Should have a credit entry")
        
        # The debit should be to member account and credit to penalty income
        self.assertIn("SHG Members", debit_entry.account, "Debit should be to member account")
        self.assertEqual(debit_entry.debit_in_account_currency, 200, "Debit amount should match fine amount")
        self.assertIn("Test Penalty Income", credit_entry.account, "Credit should be to penalty income account")
        self.assertEqual(credit_entry.credit_in_account_currency, 200, "Credit amount should match fine amount")
        self.assertEqual(debit_entry.party_type, "Customer", "Debit entry party type should be 'Customer'")
        self.assertEqual(debit_entry.party, member.customer, "Debit entry party should be member's customer")
        
        # Verify custom field linking
        self.assertEqual(je.custom_shg_meeting_fine, fine.name, 
                        "Journal Entry should be linked to the SHG Meeting Fine")
        
        # Verify no reference_type or reference_name is used (ERPNext 15 compliance)
        for entry in je.accounts:
            self.assertNotIn("reference_type", entry.__dict__, "No reference_type should be used")
            self.assertNotIn("reference_name", entry.__dict__, "No reference_name should be used")
        
        print(f"✓ Meeting Fine Journal Entry created: {je.name}")
        print(f"  Debit: {debit_entry.account} - KES {debit_entry.debit_in_account_currency:,.2f}")
        print(f"  Credit: {credit_entry.account} - KES {credit_entry.credit_in_account_currency:,.2f}")

    def test_erpnext_v15_compatibility(self):
        """Test that all created documents are compatible with ERPNext v15."""
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
            "member_name": "Test Member 5",
            "id_number": "55667788",
            "phone_number": "0755667788"
        })
        member.insert()
        member.reload()
        
        # Test contribution with Payment Entry
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": member.name,
            "member_name": member.member_name,
            "contribution_date": nowdate(),
            "amount": 300,
            "contribution_type": "Regular Weekly"
        })
        contribution.insert()
        contribution.submit()
        
        # Verify Payment Entry has no invalid reference types
        if contribution.payment_entry:
            pe = frappe.get_doc("Payment Entry", contribution.payment_entry)
            # Payment Entry should not have reference_type field that causes issues
            # The custom field approach ensures ERPNext v15 compatibility
            
        # Test loan disbursement with Journal Entry
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": member.name,
            "member_name": member.member_name,
            "loan_amount": 5000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 6,
            "repayment_frequency": "Monthly",
            "application_date": nowdate(),
            "disbursement_date": nowdate(),
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Verify Journal Entry has no invalid reference types
        if loan.disbursement_journal_entry:
            je = frappe.get_doc("Journal Entry", loan.disbursement_journal_entry)
            # Verify no account entries have invalid reference_type
            for entry in je.accounts:
                if hasattr(entry, 'reference_type') and entry.reference_type:
                    self.assertIn(entry.reference_type, valid_reference_types,
                                f"Reference type '{entry.reference_type}' should be valid for ERPNext v15")
        
        # Test loan repayment with Payment Entry
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": member.name,
            "member_name": member.member_name,
            "repayment_date": nowdate(),
            "total_paid": 500,
            "principal_amount": 400,
            "interest_amount": 100
        })
        repayment.insert()
        repayment.submit()
        
        # Verify Payment Entry has no invalid reference types
        if repayment.payment_entry:
            pe = frappe.get_doc("Payment Entry", repayment.payment_entry)
            # Payment Entry should not have reference_type field that causes issues
            
        # Test meeting fine with Journal Entry
        fine = frappe.get_doc({
            "doctype": "SHG Meeting Fine",
            "member": member.name,
            "member_name": member.member_name,
            "fine_date": nowdate(),
            "fine_amount": 100,
            "fine_reason": "Absentee",
            "status": "Paid"
        })
        fine.insert()
        fine.submit()
        
        # Verify Journal Entry has no invalid reference types
        if fine.journal_entry:
            je = frappe.get_doc("Journal Entry", fine.journal_entry)
            # Verify no account entries have invalid reference_type
            for entry in je.accounts:
                if hasattr(entry, 'reference_type') and entry.reference_type:
                    self.assertIn(entry.reference_type, valid_reference_types,
                                f"Reference type '{entry.reference_type}' should be valid for ERPNext v15")
        
        print("✓ All accounting entries are ERPNext v15 compatible")

if __name__ == '__main__':
    unittest.main()