import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from shg.shg.utils.company_utils import get_default_company


class SHGPaymentEntry(Document):
    def before_validate(self):
        """Pull company from SHG Settings and auto-fill member_name"""
        self.company = self.company or get_default_company()
        
        # Auto-fill member_name if party_type is SHG Member
        if self.party_type == "SHG Member" and self.party:
            if not self.party_name:
                self.party_name = frappe.db.get_value("SHG Member", self.party, "member_name")
        
        # Ensure amount is flt
        if self.paid_amount:
            self.paid_amount = flt(self.paid_amount)
        if self.received_amount:
            self.received_amount = flt(self.received_amount)
        
        # Calculate outstanding amount
        self.calculate_outstanding()
    
    def validate(self):
        """Validate payment entry"""
        # Ensure amount > 0
        if flt(self.paid_amount) <= 0:
            frappe.throw(_("Paid amount must be greater than zero"))
            
        # Ensure mode_of_payment not empty
        if not self.mode_of_payment:
            frappe.throw(_("Mode of Payment is required"))
            
        # Validate referenced document exists and has outstanding amount
        if self.reference_doctype and self.reference_name:
            from shg.shg.utils.payment_utils import get_outstanding
            try:
                outstanding = get_outstanding(self.reference_doctype, self.reference_name)
                if outstanding <= 0:
                    frappe.throw(_("Referenced document has no outstanding amount"))
            except Exception:
                frappe.throw(_("Referenced document {0} {1} does not exist").format(
                    self.reference_doctype, self.reference_name))
    
    def on_submit(self):
        """Process single payment"""
        from shg.shg.utils.payment_utils import process_single_payment
        payment_entry_name = process_single_payment(self.name)
        
        # Update display fields
        self.update_display_fields(payment_entry_name)
    
    def on_cancel(self):
        """Cancel linked Payment Entry"""
        # Note: In a real implementation, you would need to implement cancel functionality
        # For now, we'll just update the status
        self.db_set("status", "Cancelled")
        self.db_set("payment_status", "Cancelled")
    
    def calculate_outstanding(self):
        """Calculate outstanding amount for the referenced document"""
        if self.reference_doctype and self.reference_name:
            from shg.shg.utils.payment_utils import get_outstanding
            try:
                self.outstanding_amount = get_outstanding(self.reference_doctype, self.reference_name)
            except Exception:
                self.outstanding_amount = 0
    
    def update_display_fields(self, payment_entry_name):
        """Update display fields after submission"""
        # Set linked payment entry
        self.db_set("payment_entry", payment_entry_name)
        self.db_set("linked_payment_entry", payment_entry_name)
        
        # Set payment status
        if self.reference_doctype and self.reference_name:
            status = frappe.db.get_value(self.reference_doctype, self.reference_name, "status")
            self.db_set("payment_status", status)
        
        # Set is_closed flag
        if self.reference_doctype and self.reference_name:
            if frappe.db.has_column(self.reference_doctype, "is_closed"):
                is_closed = frappe.db.get_value(self.reference_doctype, self.reference_name, "is_closed")
                self.db_set("is_closed", is_closed or 0)
        
        # Set posted_to_gl flag
        if payment_entry_name:
            # Check if payment entry has been posted to GL
            pe = frappe.get_doc("Payment Entry", payment_entry_name)
            self.db_set("posted_to_gl", 1 if pe.docstatus == 1 else 0)
            
            # Get linked GL entries
            gl_entries = frappe.db.get_all("GL Entry", 
                                         filters={"voucher_type": "Payment Entry", "voucher_no": payment_entry_name},
                                         pluck="name")
            if gl_entries:
                self.db_set("linked_gl_entries", ", ".join(gl_entries))