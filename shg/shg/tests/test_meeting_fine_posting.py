import frappe
import unittest
from frappe.utils import nowdate

class TestMeetingFinePosting(unittest.TestCase):
    """Test cases for SHG Meeting Fine posting with proper reference types."""
    
    def setUp(self):
        """Set up test data before each test."""
        # Create a test member
        if not frappe.db.exists("SHG Member", "_Test Member"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member",
                "membership_status": "Active"
            })
            member.insert(ignore_permissions=True)
            
        # Create a test meeting
        if not frappe.db.exists("SHG Meeting", "_Test Meeting"):
            meeting = frappe.get_doc({
                "doctype": "SHG Meeting",
                "meeting_date": nowdate(),
                "meeting_title": "_Test Meeting"
            })
            meeting.insert(ignore_permissions=True)
    
    def tearDown(self):
        """Clean up test data after each test."""
        # Clean up created documents
        frappe.db.sql("DELETE FROM `tabSHG Meeting Fine` WHERE member = '_Test Member'")
        frappe.db.sql("DELETE FROM `tabSHG Meeting` WHERE meeting_title = '_Test Meeting'")
        frappe.db.sql("DELETE FROM `tabSHG Member` WHERE member_name = '_Test Member'")
        frappe.db.commit()
    
    def test_meeting_fine_creation_and_posting(self):
        """Test that creating and posting a meeting fine works correctly."""
        # Create a meeting fine
        fine = frappe.get_doc({
            "doctype": "SHG Meeting Fine",
            "meeting": "_Test Meeting",
            "member": "_Test Member",
            "member_name": "_Test Member",
            "fine_date": nowdate(),
            "fine_reason": "Late Arrival",
            "fine_amount": 50,
            "status": "Paid",
            "paid_date": nowdate()
        })
        fine.insert(ignore_permissions=True)
        fine.submit()
        
        # Check that the fine was created successfully
        self.assertIsNotNone(fine.name)
        
        # Check that GL entries were created
        self.assertTrue(fine.journal_entry)
        
        # Check that the journal entry has proper reference types
        je = frappe.get_doc("Journal Entry", fine.journal_entry)
        for entry in je.accounts:
            if entry.reference_type:
                self.assertIn(entry.reference_type, [
                    "", "Sales Invoice", "Purchase Invoice", "Journal Entry", "Sales Order",
                    "Purchase Order", "Expense Claim", "Asset", "Loan", "Payroll Entry",
                    "Employee Advance", "Exchange Rate Revaluation", "Invoice Discounting",
                    "Fees", "Full and Final Statement", "Payment Entry", "Loan Interest Accrual"
                ])
                # Check that reference_name points to the SHG Meeting Fine
                self.assertEqual(entry.reference_name, fine.name)
    
    def test_meeting_fine_payment_processing(self):
        """Test that processing a meeting fine payment works correctly."""
        # Create a meeting fine
        fine = frappe.get_doc({
            "doctype": "SHG Meeting Fine",
            "meeting": "_Test Meeting",
            "member": "_Test Member",
            "member_name": "_Test Member",
            "fine_date": nowdate(),
            "fine_reason": "Late Arrival",
            "fine_amount": 50,
            "status": "Pending"
        })
        fine.insert(ignore_permissions=True)
        fine.submit()
        
        # Create a payment entry for the fine
        payment_entry = frappe.get_doc({
            "doctype": "SHG Payment Entry",
            "member": "_Test Member",
            "member_name": "_Test Member",
            "payment_date": nowdate(),
            "payment_method": "Cash",
            "total_amount": 50,
            "payment_entries": [{
                "invoice_type": "SHG Meeting Fine",
                "reference_name": fine.name,
                "amount": 50
            }]
        })
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        # Check that the fine was marked as paid
        fine.reload()
        self.assertEqual(fine.status, "Paid")
        
        # Check that GL entries were created
        self.assertTrue(fine.journal_entry)

# Run tests if executed directly
if __name__ == '__main__':
    unittest.main()
