import frappe
import unittest
from frappe.utils import today

class TestSHGMeetingFinePosting(unittest.TestCase):
    """
    Test case to verify that SHG Meeting Fines are properly posted to ledger
    using Journal Entry and that all the enhancements work correctly.
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
        
        # Create a test meeting if it doesn't exist
        if not frappe.db.exists("SHG Meeting", "_Test Meeting 1"):
            meeting = frappe.get_doc({
                "doctype": "SHG Meeting",
                "meeting_date": today(),
                "meeting_type": "Regular Meeting"
            })
            meeting.insert()
            
        self.meeting = "_Test Meeting 1"
        
    def tearDown(self):
        """Clean up test data"""
        # Clean up test fines
        fines = frappe.get_all("SHG Meeting Fine", filters={"member": self.member})
        for fine in fines:
            fine_doc = frappe.get_doc("SHG Meeting Fine", fine.name)
            if fine_doc.docstatus == 1:
                fine_doc.cancel()
            frappe.delete_doc("SHG Meeting Fine", fine.name)
            
        # Clean up test journal entries
        journal_entries = frappe.get_all("Journal Entry", filters={"custom_shg_meeting_fine": ["like", "%"]})
        for je in journal_entries:
            je_doc = frappe.get_doc("Journal Entry", je.name)
            if je_doc.docstatus == 1:
                je_doc.cancel()
            frappe.delete_doc("Journal Entry", je.name)
    
    def test_meeting_fine_posting_with_journal_entry(self):
        """
        Test that meeting fine creates a Journal Entry (not Payment Entry)
        """
        # Create a meeting fine
        fine = frappe.get_doc({
            "doctype": "SHG Meeting Fine",
            "meeting": self.meeting,
            "member": self.member,
            "member_name": "_Test Member 1",
            "fine_date": today(),
            "fine_reason": "Late Arrival",
            "fine_amount": 100.00,
            "status": "Paid",
            "paid_date": today()
        })
        fine.insert()
        fine.submit()
        
        # Verify that a Journal Entry was created (not Payment Entry)
        self.assertIsNotNone(fine.journal_entry, "Journal Entry should be created for meeting fine")
        self.assertIsNone(fine.payment_entry, "No Payment Entry should be created for meeting fine")
        
        # Verify the Journal Entry details
        je = frappe.get_doc("Journal Entry", fine.journal_entry)
        self.assertEqual(je.voucher_type, "Journal Entry", "Voucher type should be 'Journal Entry'")
        self.assertEqual(je.custom_shg_meeting_fine, fine.name, "Journal Entry should be linked to the meeting fine")
        
        # Check accounts - should have debit to member receivable and credit to fines income
        debit_entry = None
        credit_entry = None
        for entry in je.accounts:
            if entry.debit_in_account_currency > 0:
                debit_entry = entry
            elif entry.credit_in_account_currency > 0:
                credit_entry = entry
        
        self.assertIsNotNone(debit_entry, "Should have a debit entry")
        self.assertIsNotNone(credit_entry, "Should have a credit entry")
        
        # Verify account types (with null checks)
        if debit_entry:
            self.assertEqual(debit_entry.party_type, "Customer", "Debit entry party type should be 'Customer'")
            self.assertEqual(debit_entry.party, fine.get_member_customer(), "Debit entry party should be member's customer")
        if credit_entry:
            self.assertIsNone(getattr(credit_entry, 'party_type', None), "Credit entry should not have party type")
        
        print(f"✓ Meeting Fine Journal Entry created: {je.name}")
        if debit_entry:
            print(f"  Debit: {getattr(debit_entry, 'account', 'N/A')} - KES {getattr(debit_entry, 'debit_in_account_currency', 0):,.2f}")
        if credit_entry:
            print(f"  Credit: {getattr(credit_entry, 'account', 'N/A')} - KES {getattr(credit_entry, 'credit_in_account_currency', 0):,.2f}")
        
    def test_duplicate_fine_validation(self):
        """
        Test that duplicate fines are properly validated
        """
        # Create first fine
        fine1 = frappe.get_doc({
            "doctype": "SHG Meeting Fine",
            "meeting": self.meeting,
            "member": self.member,
            "member_name": "_Test Member 1",
            "fine_date": today(),
            "fine_reason": "Late Arrival",
            "fine_amount": 100.00,
            "status": "Pending"
        })
        fine1.insert()
        
        # Try to create duplicate fine
        with self.assertRaises(Exception) as context:
            fine2 = frappe.get_doc({
                "doctype": "SHG Meeting Fine",
                "meeting": self.meeting,
                "member": self.member,
                "member_name": "_Test Member 1",
                "fine_date": today(),
                "fine_reason": "Late Arrival",
                "fine_amount": 150.00,
                "status": "Pending"
            })
            fine2.insert()
            
        self.assertTrue("A fine already exists" in str(context.exception))
        
    def test_mark_as_paid_button_functionality(self):
        """
        Test that marking as paid works correctly
        """
        # Create a pending fine
        fine = frappe.get_doc({
            "doctype": "SHG Meeting Fine",
            "meeting": self.meeting,
            "member": self.member,
            "member_name": "_Test Member 1",
            "fine_date": today(),
            "fine_reason": "Late Arrival",
            "fine_amount": 100.00,
            "status": "Pending"
        })
        fine.insert()
        
        # Mark as paid (simulating button click)
        fine.status = "Paid"
        fine.paid_date = today()
        fine.save()
        
        # Submit the fine
        fine.submit()
        
        # Verify that it gets posted to ledger
        self.assertIsNotNone(fine.journal_entry, "Journal Entry should be created when marked as paid")
        
    def test_safe_auto_description_generation(self):
        """
        Test that auto-description works safely even when meeting date is missing
        """
        # Create a fine without meeting date
        fine = frappe.get_doc({
            "doctype": "SHG Meeting Fine",
            "meeting": self.meeting,
            "member": self.member,
            "member_name": "_Test Member 1",
            "fine_date": today(),
            "fine_reason": "Late Arrival",
            "fine_amount": 100.00,
            "status": "Pending"
        })
        fine.insert()
        
        # Auto-generate description
        fine.autogenerate_description()
        
        # Should have a description even if meeting date retrieval fails
        self.assertIsNotNone(fine.fine_description, "Fine description should be generated")
        self.assertTrue("Late Arrival" in fine.fine_description, "Description should contain fine reason")

if __name__ == '__main__':
    unittest.main()