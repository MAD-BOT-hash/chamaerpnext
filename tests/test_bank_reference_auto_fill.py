import unittest
import frappe
from frappe.utils import nowdate, add_days

class TestBankReferenceAutoFill(unittest.TestCase):
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

    def test_contribution_payment_entry_reference_fields(self):
        """Test that Payment Entry for SHG Contribution auto-fills reference fields."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Contribution",
            "id_number": "12345678",
            "phone_number": "0712345678"
        })
        member.insert()
        member.reload()
        
        # Update SHG Settings to use Payment Entry for contributions
        settings = frappe.get_single("SHG Settings")
        settings.contribution_posting_method = "Payment Entry"
        settings.save()
        
        # Create a contribution (will use Payment Entry)
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
        
        # Verify the Payment Entry details
        pe = frappe.get_doc("Payment Entry", contribution.payment_entry)
        self.assertEqual(pe.payment_type, "Receive", "Payment type should be 'Receive' for contributions")
        self.assertEqual(pe.voucher_type, "Bank Entry", "Voucher type should be 'Bank Entry'")
        
        # Check that reference fields are auto-populated
        self.assertEqual(pe.reference_no, contribution.name, "Reference No should match contribution name")
        self.assertEqual(pe.reference_date, contribution.contribution_date, "Reference Date should match contribution date")
        
        print(f"✓ Payment Entry created with auto-filled reference fields: {pe.name}")
        print(f"  Reference No: {pe.reference_no}")
        print(f"  Reference Date: {pe.reference_date}")

    def test_loan_payment_entry_reference_fields(self):
        """Test that Payment Entry for SHG Loan disbursement auto-fills reference fields."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Loan",
            "id_number": "87654321",
            "phone_number": "0787654321"
        })
        member.insert()
        member.reload()
        
        # Update SHG Settings to use Payment Entry for loan disbursement
        settings = frappe.get_single("SHG Settings")
        settings.loan_disbursement_posting_method = "Payment Entry"
        settings.save()
        
        # Create a loan (will use Payment Entry)
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
        
        # Verify that a Payment Entry was created
        self.assertIsNotNone(loan.disbursement_payment_entry, "Payment Entry should be created for loan disbursement")
        
        # Verify the Payment Entry details
        pe = frappe.get_doc("Payment Entry", loan.disbursement_payment_entry)
        self.assertEqual(pe.payment_type, "Pay", "Payment type should be 'Pay' for loan disbursement")
        self.assertEqual(pe.voucher_type, "Bank Entry", "Voucher type should be 'Bank Entry'")
        
        # Check that reference fields are auto-populated
        self.assertEqual(pe.reference_no, loan.name, "Reference No should match loan name")
        self.assertEqual(pe.reference_date, loan.disbursement_date, "Reference Date should match disbursement date")
        
        print(f"✓ Payment Entry created with auto-filled reference fields: {pe.name}")
        print(f"  Reference No: {pe.reference_no}")
        print(f"  Reference Date: {pe.reference_date}")

    def test_manual_reference_fields_not_overwritten(self):
        """Test that manually entered reference fields are not overwritten."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Manual Ref",
            "id_number": "11223344",
            "phone_number": "0711223344"
        })
        member.insert()
        member.reload()
        
        # Update SHG Settings to use Payment Entry for contributions
        settings = frappe.get_single("SHG Settings")
        settings.contribution_posting_method = "Payment Entry"
        settings.save()
        
        # Create a contribution (will use Payment Entry)
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
        
        # Manually update the Payment Entry with custom reference fields
        pe = frappe.get_doc("Payment Entry", contribution.payment_entry)
        original_ref_no = "MANUAL-REF-001"
        original_ref_date = add_days(nowdate(), -1)
        
        pe.reference_no = original_ref_no
        pe.reference_date = original_ref_date
        pe.save()
        
        # Reload and verify that our manual values were preserved
        pe.reload()
        self.assertEqual(pe.reference_no, original_ref_no, "Manual Reference No should be preserved")
        self.assertEqual(pe.reference_date, original_ref_date, "Manual Reference Date should be preserved")
        
        print(f"✓ Manual reference fields preserved: {pe.name}")
        print(f"  Reference No: {pe.reference_no}")
        print(f"  Reference Date: {pe.reference_date}")

if __name__ == '__main__':
    unittest.main()