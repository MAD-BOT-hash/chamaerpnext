import frappe
import unittest
from frappe.utils import today, add_days
from frappe.test_runner import make_test_objects

class TestSHGWorkflow(unittest.TestCase):
    def setUp(self):
        # Create test data
        self.create_test_member()
        self.create_test_contribution_type()
        self.setup_shg_settings()
        
    def tearDown(self):
        # Clean up test data
        pass
        
    def create_test_member(self):
        """Create a test SHG Member"""
        if not frappe.db.exists("SHG Member", "Test Member"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "Test Member",
                "membership_status": "Active",
                "phone_number": "0712345678",
                "email": "test@example.com"
            })
            member.insert(ignore_permissions=True)
            frappe.db.commit()
            
        self.member_name = "Test Member"
        
    def create_test_contribution_type(self):
        """Create a test SHG Contribution Type"""
        if not frappe.db.exists("SHG Contribution Type", "Regular Weekly"):
            contrib_type = frappe.get_doc({
                "doctype": "SHG Contribution Type",
                "contribution_type_name": "Regular Weekly",
                "default_amount": 500,
                "item_code": "SHG-CONTRIB-WK"
            })
            contrib_type.insert(ignore_permissions=True)
            frappe.db.commit()
            
    def setup_shg_settings(self):
        """Setup SHG Settings for testing"""
        settings = frappe.get_single("SHG Settings")
        settings.default_contribution_payment_method = "Cash"
        settings.default_income_account = "SHG Contributions - _TC"
        settings.default_receivable_account = "Debtors - _TC"
        settings.default_bank_account = "Cash - _TC"
        settings.auto_generate_sales_invoice = 1
        settings.auto_create_contribution_on_invoice_submit = 1
        settings.auto_apply_payment_on_payment_entry_submit = 1
        settings.apply_late_fee_policy = 1
        settings.late_fee_rate = 5
        settings.save()
        frappe.db.commit()
        
    def test_shg_contribution_invoice_workflow(self):
        """Test the complete SHG Contribution Invoice workflow"""
        # Create SHG Contribution Invoice
        invoice = frappe.get_doc({
            "doctype": "SHG Contribution Invoice",
            "member": self.member_name,
            "member_name": "Test Member",
            "invoice_date": today(),
            "due_date": today(),
            "contribution_type": "Regular Weekly",
            "amount": 500,
            "payment_method": "Cash",
            "status": "Draft"
        })
        invoice.insert(ignore_permissions=True)
        
        # Submit the invoice
        invoice.submit()
        
        # Verify Sales Invoice was created
        self.assertTrue(invoice.sales_invoice)
        self.assertTrue(invoice.linked_sales_invoice)
        
        # Verify SHG Contribution was created
        self.assertTrue(invoice.linked_shg_contribution)
        
        # Verify statuses
        self.assertEqual(invoice.status, "Unpaid")
        
        # Get the created Sales Invoice
        sales_invoice = frappe.get_doc("Sales Invoice", invoice.sales_invoice)
        self.assertEqual(sales_invoice.outstanding_amount, 500)
        
        # Get the created SHG Contribution
        contribution = frappe.get_doc("SHG Contribution", invoice.linked_shg_contribution)
        self.assertEqual(contribution.status, "Unpaid")
        self.assertEqual(contribution.amount, 500)
        
    def test_payment_entry_workflow(self):
        """Test the Payment Entry workflow"""
        # First create and submit a contribution invoice
        invoice = frappe.get_doc({
            "doctype": "SHG Contribution Invoice",
            "member": self.member_name,
            "member_name": "Test Member",
            "invoice_date": today(),
            "due_date": today(),
            "contribution_type": "Regular Weekly",
            "amount": 500,
            "payment_method": "Cash",
            "status": "Draft"
        })
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        
        # Create Payment Entry
        payment = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "party_type": "Customer",
            "party": frappe.get_doc("SHG Member", self.member_name).customer,
            "paid_from": "Debtors - _TC",
            "paid_to": "Cash - _TC",
            "paid_amount": 500,
            "received_amount": 500,
            "reference_no": "TEST-001",
            "reference_date": today(),
            "references": [{
                "reference_doctype": "Sales Invoice",
                "reference_name": invoice.sales_invoice,
                "allocated_amount": 500
            }]
        })
        payment.insert(ignore_permissions=True)
        payment.submit()
        
        # Verify statuses are updated
        invoice.reload()
        contribution = frappe.get_doc("SHG Contribution", invoice.linked_shg_contribution)
        contribution.reload()
        sales_invoice = frappe.get_doc("Sales Invoice", invoice.sales_invoice)
        sales_invoice.reload()
        
        # All should be marked as Paid
        self.assertEqual(invoice.status, "Paid")
        self.assertEqual(contribution.status, "Paid")
        self.assertEqual(sales_invoice.outstanding_amount, 0)
        
    def test_overdue_invoice_workflow(self):
        """Test the overdue invoice workflow"""
        # Create an overdue invoice
        past_date = add_days(today(), -30)
        invoice = frappe.get_doc({
            "doctype": "SHG Contribution Invoice",
            "member": self.member_name,
            "member_name": "Test Member",
            "invoice_date": past_date,
            "due_date": past_date,
            "contribution_type": "Regular Weekly",
            "amount": 500,
            "payment_method": "Cash",
            "status": "Draft"
        })
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        
        # Run the overdue invoice marking function
        from shg.shg.doctype.shg_contribution_invoice.shg_contribution_invoice import mark_overdue_invoices
        mark_overdue_invoices()
        
        # Reload and verify status
        invoice.reload()
        self.assertEqual(invoice.status, "Overdue")
