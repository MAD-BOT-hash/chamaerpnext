import unittest
import frappe
from frappe.utils import nowdate, add_days

class TestBankEntryReferences(unittest.TestCase):
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

    def test_bank_entry_reference_fields(self):
        """Test that Bank Entry voucher types have required reference fields."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Bank Entry",
            "id_number": "12345678",
            "phone_number": "0712345678"
        })
        member.insert()
        member.reload()
        
        # Update SHG Settings to use Journal Entry for contributions
        settings = frappe.get_single("SHG Settings")
        settings.contribution_posting_method = "Journal Entry"
        settings.save()
        
        # Create a contribution (will use Bank Entry voucher type)
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
        
        # Verify that a Journal Entry was created
        self.assertIsNotNone(contribution.journal_entry, "Journal Entry should be created for contribution")
        
        # Verify the Journal Entry details
        je = frappe.get_doc("Journal Entry", contribution.journal_entry)
        self.assertEqual(je.voucher_type, "Bank Entry", "Voucher type should be 'Bank Entry'")
        
        # Check that reference fields are populated for Bank Entry
        self.assertEqual(je.reference_no, contribution.name, "Reference No should match contribution name")
        self.assertEqual(je.reference_date, contribution.contribution_date, "Reference Date should match contribution date")
        
        print(f"✓ Bank Entry created with required reference fields: {je.name}")
        print(f"  Reference No: {je.reference_no}")
        print(f"  Reference Date: {je.reference_date}")

    def test_cash_entry_reference_fields(self):
        """Test that Cash Entry voucher types have required reference fields."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Cash Entry",
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
        
        # Update SHG Settings to use Journal Entry for loan repayments
        settings = frappe.get_single("SHG Settings")
        settings.loan_repayment_posting_method = "Journal Entry"
        settings.save()
        
        # Create a loan repayment (will use Cash Entry voucher type)
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": member.name,
            "member_name": member.member_name,
            "repayment_date": add_days(nowdate(), 30),
            "total_paid": 1000,
            "principal_amount": 800,
            "interest_amount": 200
        })
        repayment.insert()
        repayment.submit()
        
        # Verify that a Journal Entry was created
        self.assertIsNotNone(repayment.journal_entry, "Journal Entry should be created for loan repayment")
        
        # Verify the Journal Entry details
        je = frappe.get_doc("Journal Entry", repayment.journal_entry)
        self.assertEqual(je.voucher_type, "Cash Entry", "Voucher type should be 'Cash Entry'")
        
        # Check that reference fields are populated for Cash Entry
        self.assertEqual(je.reference_no, repayment.name, "Reference No should match repayment name")
        self.assertEqual(je.reference_date, repayment.repayment_date, "Reference Date should match repayment date")
        
        print(f"✓ Cash Entry created with required reference fields: {je.name}")
        print(f"  Reference No: {je.reference_no}")
        print(f"  Reference Date: {je.reference_date}")

    def test_journal_entry_without_reference_fields(self):
        """Test that regular Journal Entry voucher types don't require reference fields."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Journal Entry",
            "id_number": "11223344",
            "phone_number": "0711223344"
        })
        member.insert()
        member.reload()
        
        # Create a meeting
        meeting = frappe.get_doc({
            "doctype": "SHG Meeting",
            "meeting_date": nowdate(),
            "meeting_type": "Regular Meeting"
        })
        meeting.insert()
        meeting.submit()
        
        # Create a meeting fine (will use Journal Entry voucher type)
        fine = frappe.get_doc({
            "doctype": "SHG Meeting Fine",
            "meeting": meeting.name,
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
        
        # Verify the Journal Entry details
        je = frappe.get_doc("Journal Entry", fine.journal_entry)
        self.assertEqual(je.voucher_type, "Journal Entry", "Voucher type should be 'Journal Entry'")
        
        # Check that reference fields are not required for regular Journal Entry
        # They may be empty or not set
        print(f"✓ Regular Journal Entry created without required reference fields: {je.name}")
        print(f"  Voucher Type: {je.voucher_type}")

if __name__ == '__main__':
    unittest.main()