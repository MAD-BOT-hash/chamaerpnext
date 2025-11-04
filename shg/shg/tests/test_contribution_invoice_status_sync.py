import frappe
import unittest
from frappe.utils import nowdate

class TestContributionInvoiceStatusSync(unittest.TestCase):
    """Test cases for SHG Contribution Invoice and Contribution status synchronization."""
    
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
            
        # Create a test contribution type
        if not frappe.db.exists("SHG Contribution Type", "_Test Contribution Type"):
            contrib_type = frappe.get_doc({
                "doctype": "SHG Contribution Type",
                "contribution_type_name": "_Test Contribution Type",
                "default_amount": 100
            })
            contrib_type.insert(ignore_permissions=True)
    
    def tearDown(self):
        """Clean up test data after each test."""
        # Clean up created documents
        frappe.db.sql("DELETE FROM `tabSHG Contribution Invoice` WHERE member = '_Test Member'")
        frappe.db.sql("DELETE FROM `tabSHG Contribution` WHERE member = '_Test Member'")
        frappe.db.commit()
    
    def test_contribution_invoice_creates_linked_contribution(self):
        """Test that submitting a contribution invoice creates a linked contribution."""
        # Create and submit a contribution invoice
        invoice = frappe.get_doc({
            "doctype": "SHG Contribution Invoice",
            "member": "_Test Member",
            "member_name": "_Test Member",
            "invoice_date": nowdate(),
            "due_date": nowdate(),
            "amount": 100,
            "contribution_type": "_Test Contribution Type",
            "status": "Unpaid"
        })
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        
        # Check that a linked contribution was created
        contribution_name = frappe.db.get_value("SHG Contribution", 
                                              {"invoice_reference": invoice.name})
        self.assertIsNotNone(contribution_name)
        
        # Check that the contribution status is Unpaid
        contribution = frappe.get_doc("SHG Contribution", contribution_name)
        self.assertEqual(contribution.status, "Unpaid")
    
    def test_paid_and_closed_invoice_marks_contribution_as_paid(self):
        """Test that marking an invoice as Paid and Closed marks the contribution as Paid."""
        # Create and submit a contribution invoice
        invoice = frappe.get_doc({
            "doctype": "SHG Contribution Invoice",
            "member": "_Test Member",
            "member_name": "_Test Member",
            "invoice_date": nowdate(),
            "due_date": nowdate(),
            "amount": 100,
            "contribution_type": "_Test Contribution Type",
            "status": "Unpaid"
        })
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        
        # Get the linked contribution
        contribution_name = frappe.db.get_value("SHG Contribution", 
                                              {"invoice_reference": invoice.name})
        self.assertIsNotNone(contribution_name)
        
        # Mark invoice as Paid and Closed
        invoice.db_set("status", "Paid")
        if frappe.db.has_column("SHG Contribution Invoice", "is_closed"):
            invoice.db_set("is_closed", 1)
        
        # Call the method to mark contribution as paid
        invoice.mark_linked_contribution_as_paid()
        
        # Check that the contribution status is now Paid
        contribution = frappe.get_doc("SHG Contribution", contribution_name)
        self.assertEqual(contribution.status, "Paid")
    
    def test_reopening_invoice_reopens_contribution(self):
        """Test that reopening an invoice reopens the contribution."""
        # Create and submit a contribution invoice
        invoice = frappe.get_doc({
            "doctype": "SHG Contribution Invoice",
            "member": "_Test Member",
            "member_name": "_Test Member",
            "invoice_date": nowdate(),
            "due_date": nowdate(),
            "amount": 100,
            "contribution_type": "_Test Contribution Type",
            "status": "Unpaid"
        })
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        
        # Get the linked contribution
        contribution_name = frappe.db.get_value("SHG Contribution", 
                                              {"invoice_reference": invoice.name})
        self.assertIsNotNone(contribution_name)
        
        # First mark invoice as Paid and Closed
        invoice.db_set("status", "Paid")
        if frappe.db.has_column("SHG Contribution Invoice", "is_closed"):
            invoice.db_set("is_closed", 1)
        invoice.mark_linked_contribution_as_paid()
        
        # Check that contribution is Paid
        contribution = frappe.get_doc("SHG Contribution", contribution_name)
        self.assertEqual(contribution.status, "Paid")
        
        # Now reopen the invoice
        invoice.db_set("status", "Unpaid")
        if frappe.db.has_column("SHG Contribution Invoice", "is_closed"):
            invoice.db_set("is_closed", 0)
        invoice.reopen_linked_contribution()
        
        # Check that the contribution status is now Unpaid
        contribution.reload()
        self.assertEqual(contribution.status, "Unpaid")

# Run tests if executed directly
if __name__ == '__main__':
    unittest.main()