import frappe
import unittest

class TestAccountResolution(unittest.TestCase):
    def setUp(self):
        # Create a test company if it doesn't exist
        if not frappe.db.exists("Company", "Test Company"):
            company = frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "abbr": "TC",
                "default_currency": "KES",
                "country": "Kenya"
            })
            company.insert()

        # Create a test member if it doesn't exist
        if not frappe.db.exists("SHG Member", "TEST001"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_id": "TEST001",
                "member_name": "Test Member",
                "membership_status": "Active"
            })
            member.insert()

    def test_get_account_creates_parent_accounts(self):
        from shg.shg.utils.account_utils import get_account
        
        # This should create the parent account if it doesn't exist
        company = "Test Company"
        
        # First, we need to ensure Accounts Receivable exists
        ar_account = frappe.db.exists("Account", {"account_name": "Accounts Receivable - TC", "company": company})
        if not ar_account:
            # Create Accounts Receivable parent
            ar = frappe.get_doc({
                "doctype": "Account",
                "account_name": "Accounts Receivable - TC",
                "company": company,
                "is_group": 1,
                "account_type": "Receivable",
                "root_type": "Asset"
            })
            ar.insert()
        
        # Test getting/creating loans receivable account
        account = get_account(company, "loans_receivable")
        self.assertIsNotNone(account)
        
        # Test getting/creating member-specific account
        member_account = get_account(company, "loans_receivable", "TEST001")
        self.assertIsNotNone(member_account)

    def tearDown(self):
        # Clean up test data
        if frappe.db.exists("SHG Member", "TEST001"):
            frappe.delete_doc("SHG Member", "TEST001")
        if frappe.db.exists("Company", "Test Company"):
            frappe.delete_doc("Company", "Test Company")

if __name__ == '__main__':
    unittest.main()