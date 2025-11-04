import frappe
import unittest
from frappe.utils import today

class TestContributionAccountDuplication(unittest.TestCase):
    """
    Test case to verify that duplicate SHG Contribution accounts are not created
    and that multiple contributions for the same company work correctly.
    """
    
    def setUp(self):
        """Set up test dependencies"""
        # Create a test company if it doesn't exist
        if not frappe.db.exists("Company", "_Test SHG Company"):
            company = frappe.get_doc({
                "doctype": "Company",
                "company_name": "_Test SHG Company",
                "abbr": "_TSC",
                "default_currency": "KES",
                "country": "Kenya"
            })
            company.insert()
        
        self.company = "_Test SHG Company"
        
        # Create a test member if it doesn't exist
        if not frappe.db.exists("SHG Member", "_Test Member 1"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member 1",
                "membership_status": "Active"
            })
            member.insert()
            
        self.member = "_Test Member 1"
        
        # Create a customer for the member if it doesn't exist
        if not frappe.db.exists("Customer", "_Test Customer 1"):
            customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": "_Test Customer 1",
                "customer_type": "Individual",
                "customer_group": "All Customer Groups",
                "territory": "All Territories"
            })
            customer.insert()
            
            # Link customer to member
            member_doc = frappe.get_doc("SHG Member", self.member)
            member_doc.customer = customer.name
            member_doc.save()
        
    def tearDown(self):
        """Clean up test data"""
        # Clean up test contributions
        contributions = frappe.get_all("SHG Contribution", filters={"member": self.member})
        for contrib in contributions:
            contrib_doc = frappe.get_doc("SHG Contribution", contrib.name)
            if contrib_doc.docstatus == 1:
                contrib_doc.cancel()
            frappe.delete_doc("SHG Contribution", contrib.name)
    
    def test_no_duplicate_accounts_on_sequential_contributions(self):
        """
        Test that submitting 3 sequential contributions for the same company
        does not create duplicate accounts.
        """
        # Get initial count of SHG Contribution accounts
        initial_accounts = frappe.get_all("Account", 
            filters={
                "company": self.company,
                "account_name": ["like", "%SHG Contributions%"]
            }
        )
        initial_count = len(initial_accounts)
        
        # Create and submit first contribution
        contribution1 = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": self.member,
            "contribution_date": today(),
            "amount": 100.00,
            "company": self.company
        })
        contribution1.insert()
        contribution1.submit()
        
        # Create and submit second contribution
        contribution2 = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": self.member,
            "contribution_date": today(),
            "amount": 150.00,
            "company": self.company
        })
        contribution2.insert()
        contribution2.submit()
        
        # Create and submit third contribution
        contribution3 = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": self.member,
            "contribution_date": today(),
            "amount": 200.00,
            "company": self.company
        })
        contribution3.insert()
        contribution3.submit()
        
        # Check that only one SHG Contributions account exists
        final_accounts = frappe.get_all("Account", 
            filters={
                "company": self.company,
                "account_name": ["like", "%SHG Contributions%"]
            }
        )
        final_count = len(final_accounts)
        
        # Should have at most one more account (the SHG Contributions account)
        self.assertLessEqual(final_count, initial_count + 1, 
            "Duplicate SHG Contribution accounts were created")
        
        # Verify that all contributions have journal entries
        self.assertTrue(contribution1.journal_entry or contribution1.payment_entry, 
            "First contribution did not create a journal or payment entry")
        self.assertTrue(contribution2.journal_entry or contribution2.payment_entry, 
            "Second contribution did not create a journal or payment entry")
        self.assertTrue(contribution3.journal_entry or contribution3.payment_entry, 
            "Third contribution did not create a journal or payment entry")
        
        # Verify all journal entries are unique
        je_list = [contribution1.journal_entry, contribution2.journal_entry, contribution3.journal_entry]
        je_list = [je for je in je_list if je]  # Remove None values
        self.assertEqual(len(je_list), len(set(je_list)), 
            "Duplicate journal entries were created for different contributions")

if __name__ == '__main__':
    unittest.main()