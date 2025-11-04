import frappe
import unittest
from frappe.utils import today

class TestContributionTypeHandling(unittest.TestCase):
    """
    Test case to verify that contribution types are properly handled
    when posting from invoices and that 'Invoice Payment' type is correctly translated.
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
        
        # Create default contribution types
        self.create_default_contribution_types()
        
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
            
        # Clean up test invoices
        invoices = frappe.get_all("SHG Contribution Invoice", filters={"member": self.member})
        for invoice in invoices:
            invoice_doc = frappe.get_doc("SHG Contribution Invoice", invoice.name)
            if invoice_doc.docstatus == 1:
                invoice_doc.cancel()
            frappe.delete_doc("SHG Contribution Invoice", invoice.name)
    
    def create_default_contribution_types(self):
        """Create default contribution types for testing"""
        default_types = [
            {
                "doctype": "SHG Contribution Type",
                "contribution_type_name": "Regular Weekly",
                "description": "Regular weekly contribution from members",
                "default_amount": 500,
                "frequency": "Weekly",
                "enabled": 1
            },
            {
                "doctype": "SHG Contribution Type",
                "contribution_type_name": "Special Assessment",
                "description": "Special assessment for specific needs",
                "frequency": "Monthly",
                "enabled": 1
            }
        ]
        
        for type_data in default_types:
            if not frappe.db.exists("SHG Contribution Type", type_data["contribution_type_name"]):
                doc = frappe.get_doc(type_data)
                doc.insert()
    
    def test_contribution_type_from_invoice(self):
        """
        Test that contribution type is correctly fetched from invoice
        """
        # Create an invoice with a valid contribution type
        invoice = frappe.get_doc({
            "doctype": "SHG Contribution Invoice",
            "member": self.member,
            "member_name": "_Test Member 1",
            "contribution_type": "Regular Weekly",
            "amount": 500.00,
            "invoice_date": today(),
            "due_date": today(),
            "status": "Unpaid"
        })
        invoice.insert()
        invoice.submit()
        
        # Post to contribution
        from shg.shg.doctype.shg_contribution_invoice.shg_contribution_invoice import post_to_contribution
        result = post_to_contribution(invoice.name)
        
        # Verify contribution was created with correct type
        contribution = frappe.get_doc("SHG Contribution", result["contribution"])
        self.assertEqual(contribution.contribution_type, "Regular Weekly")
        
    def test_invalid_contribution_type_fallback(self):
        """
        Test that invalid contribution type falls back to default
        """
        # Create an invoice with an invalid contribution type
        invoice = frappe.get_doc({
            "doctype": "SHG Contribution Invoice",
            "member": self.member,
            "member_name": "_Test Member 1",
            "contribution_type": "Invalid Type",
            "amount": 500.00,
            "invoice_date": today(),
            "due_date": today(),
            "status": "Unpaid"
        })
        invoice.insert()
        invoice.submit()
        
        # Post to contribution
        from shg.shg.doctype.shg_contribution_invoice.shg_contribution_invoice import post_to_contribution
        result = post_to_contribution(invoice.name)
        
        # Verify contribution was created with fallback type
        contribution = frappe.get_doc("SHG Contribution", result["contribution"])
        self.assertEqual(contribution.contribution_type, "Regular Weekly")
        
    def test_invoice_payment_type_translation(self):
        """
        Test that 'Invoice Payment' type is translated to a valid type
        """
        # Create a contribution with 'Invoice Payment' type
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": self.member,
            "member_name": "_Test Member 1",
            "contribution_type": "Invoice Payment",
            "amount": 500.00,
            "contribution_date": today(),
            "posting_date": today()
        })
        contribution.insert()
        
        # The validation should automatically translate 'Invoice Payment' to a valid type
        self.assertEqual(contribution.contribution_type, "Regular Weekly")

if __name__ == '__main__':
    unittest.main()