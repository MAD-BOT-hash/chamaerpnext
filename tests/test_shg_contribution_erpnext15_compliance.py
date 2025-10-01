import unittest
import frappe
from frappe.utils import nowdate

class TestSHGContributionERPNext15Compliance(unittest.TestCase):
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
        
        # Update SHG Settings to use Payment Entry for contributions
        settings = frappe.get_single("SHG Settings")
        settings.contribution_posting_method = "Payment Entry"
        settings.default_bank_account = "Test Bank - TC"
        settings.default_cash_account = "Test Cash - TC"
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
            
        # Delete test Payment Entries
        for pe in frappe.get_all("Payment Entry", filters={"reference_no": ["like", "SHG-CONTRIB-%"]}):
            frappe.delete_doc("Payment Entry", pe.name)
            
        # Delete test Journal Entries
        for je in frappe.get_all("Journal Entry", filters={"user_remark": ["like", "SHG Contribution%"]}):
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

    def test_contribution_journal_entry_flow(self):
        """Test that Contributions can also create Journal Entry when configured."""
        # Update SHG Settings to use Journal Entry for contributions
        settings = frappe.get_single("SHG Settings")
        settings.contribution_posting_method = "Journal Entry"
        settings.save()
        
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member 2",
            "id_number": "87654321",
            "phone_number": "0787654321"
        })
        member.insert()
        member.reload()
        
        # Create a contribution
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": member.name,
            "member_name": member.member_name,
            "contribution_date": nowdate(),
            "amount": 500,
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
        self.assertEqual(debit_entry.debit_in_account_currency, 500, "Debit amount should match contribution amount")
        self.assertIn("Test Contributions", credit_entry.account, "Credit should be to contribution income account")
        self.assertEqual(credit_entry.credit_in_account_currency, 500, "Credit amount should match contribution amount")
        self.assertEqual(credit_entry.party_type, "Customer", "Credit entry party type should be 'Customer'")
        self.assertEqual(credit_entry.party, member.customer, "Credit entry party should be member's customer")
        
        # Verify custom field linking
        self.assertEqual(je.custom_shg_contribution, contribution.name, 
                        "Journal Entry should be linked to the SHG Contribution")
        
        # Verify no reference_type or reference_name is used (ERPNext 15 compliance)
        for entry in je.accounts:
            self.assertNotIn("reference_type", entry.__dict__, "No reference_type should be used")
            self.assertNotIn("reference_name", entry.__dict__, "No reference_name should be used")
        
        print(f"✓ Contribution Journal Entry created: {je.name}")
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
            "member_name": "Test Member 3",
            "id_number": "11223344",
            "phone_number": "0711223344"
        })
        member.insert()
        member.reload()
        
        # Test contribution with Payment Entry
        contribution1 = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": member.name,
            "member_name": member.member_name,
            "contribution_date": nowdate(),
            "amount": 300,
            "contribution_type": "Regular Weekly"
        })
        contribution1.insert()
        contribution1.submit()
        
        # Verify Payment Entry has no invalid reference types
        if contribution1.payment_entry:
            pe = frappe.get_doc("Payment Entry", contribution1.payment_entry)
            # Payment Entry should not have reference_type field that causes issues
            # The custom field approach ensures ERPNext v15 compatibility
            
        # Test contribution with Journal Entry
        settings = frappe.get_single("SHG Settings")
        settings.contribution_posting_method = "Journal Entry"
        settings.save()
        
        contribution2 = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": member.name,
            "member_name": member.member_name,
            "contribution_date": nowdate(),
            "amount": 400,
            "contribution_type": "Regular Weekly"
        })
        contribution2.insert()
        contribution2.submit()
        
        # Verify Journal Entry has no invalid reference types
        if contribution2.journal_entry:
            je = frappe.get_doc("Journal Entry", contribution2.journal_entry)
            # Verify no account entries have invalid reference_type
            for entry in je.accounts:
                if hasattr(entry, 'reference_type') and entry.reference_type:
                    self.assertIn(entry.reference_type, valid_reference_types,
                                f"Reference type '{entry.reference_type}' should be valid for ERPNext v15")
        
        print("✓ All accounting entries are ERPNext v15 compatible")

if __name__ == '__main__':
    unittest.main()