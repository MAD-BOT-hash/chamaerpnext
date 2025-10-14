import frappe
import unittest

class TestSHGPaymentEntry(unittest.TestCase):
    def setUp(self):
        # Create test member if it doesn't exist
        if not frappe.db.exists("SHG Member", "_Test Member"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member",
                "id_number": "12345678",
                "phone_number": "0712345678",
                "membership_date": "2025-01-01",
                "membership_status": "Active"
            })
            member.insert()
            
        # Create test contribution invoice if it doesn't exist
        if not frappe.db.exists("SHG Contribution Invoice", "_Test Contribution Invoice"):
            invoice = frappe.get_doc({
                "doctype": "SHG Contribution Invoice",
                "member": "_Test Member",
                "invoice_date": "2025-01-01",
                "due_date": "2025-01-31",
                "amount": 500,
                "description": "Test contribution invoice"
            })
            invoice.insert()
            invoice.submit()
            
    def tearDown(self):
        # Clean up test data
        if frappe.db.exists("SHG Payment Entry", {"member": "_Test Member"}):
            payment_entry = frappe.get_doc("SHG Payment Entry", {"member": "_Test Member"})
            if payment_entry.docstatus == 1:
                payment_entry.cancel()
            payment_entry.delete()
            
        if frappe.db.exists("SHG Contribution Invoice", "_Test Contribution Invoice"):
            invoice = frappe.get_doc("SHG Contribution Invoice", "_Test Contribution Invoice")
            if invoice.docstatus == 1:
                invoice.cancel()
            invoice.delete()
            
        if frappe.db.exists("SHG Member", "_Test Member"):
            member = frappe.get_doc("SHG Member", "_Test Member")
            member.delete()
            
    def test_payment_entry_creation(self):
        # Create payment entry
        payment_entry = frappe.get_doc({
            "doctype": "SHG Payment Entry",
            "member": "_Test Member",
            "payment_date": "2025-01-15",
            "payment_method": "Cash",
            "debit_account": "Cash - _TC",
            "credit_account": "Accounts Receivable - _TC",
            "payment_entries": [
                {
                    "invoice_type": "SHG Contribution Invoice",
                    "invoice": "_Test Contribution Invoice",
                    "amount": 500
                }
            ]
        })
        
        payment_entry.insert()
        payment_entry.submit()
        
        # Verify payment entry was created and submitted
        self.assertEqual(payment_entry.docstatus, 1)
        self.assertEqual(payment_entry.total_amount, 500)
        
        # Verify invoice status was updated
        invoice = frappe.get_doc("SHG Contribution Invoice", "_Test Contribution Invoice")
        self.assertEqual(invoice.status, "Paid")