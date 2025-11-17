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
    
    def validate(self):
        """Validate payment entry"""
        # Ensure amount > 0
        if flt(self.paid_amount) <= 0:
            frappe.throw(_("Paid amount must be greater than zero"))
            
        # Ensure mode_of_payment not empty
        if not self.mode_of_payment:
            frappe.throw(_("Mode of Payment is required"))
            
        # Validate reference_doctype
        valid_doctypes = ["SHG Contribution Invoice", "SHG Contribution", "SHG Meeting Fine"]
        if self.reference_doctype and self.reference_doctype not in valid_doctypes:
            frappe.throw(_("Reference Doctype must be one of: {0}").format(", ".join(valid_doctypes)))
            
        # Validate referenced document exists
        if self.reference_doctype and self.reference_name:
            if not frappe.db.exists(self.reference_doctype, self.reference_name):
                frappe.throw(_("Referenced document {0} {1} does not exist").format(
                    self.reference_doctype, self.reference_name))
                    
            # Validate referenced document OUTSTANDING > 0
            from shg.shg.utils.payment_utils import get_outstanding
            outstanding = get_outstanding(self.reference_doctype, self.reference_name)
            if outstanding <= 0:
                frappe.throw(_("Referenced document has no outstanding amount"))
    
    def on_submit(self):
        """Process single payment"""
        from shg.shg.utils.payment_utils import process_single_payment
        process_single_payment(self)
    
    def on_cancel(self):
        """Cancel linked Payment Entry"""
        from shg.shg.utils.payment_utils import cancel_linked_payment_entry
        cancel_linked_payment_entry(self)