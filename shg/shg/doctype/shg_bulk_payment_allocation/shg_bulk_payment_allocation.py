import frappe
from frappe.model.document import Document
from frappe import _


class SHGBulkPaymentAllocation(Document):
    """
    SHG Bulk Payment Allocation Child Table
    Represents individual payment allocations within bulk payment
    """
    
    def validate(self):
        """Validate allocation"""
        self.validate_required_fields()
        self.validate_amounts()
        self.auto_fetch_member_name()
    
    def validate_required_fields(self):
        """Validate required fields"""
        if not self.member:
            frappe.throw(_("Member is required"))
        
        if not self.reference_doctype:
            frappe.throw(_("Reference Type is required"))
        
        if not self.reference_name:
            frappe.throw(_("Reference Name is required"))
        
        if not self.reference_date:
            frappe.throw(_("Reference Date is required"))
        
        if not self.due_date:
            frappe.throw(_("Due Date is required"))
    
    def validate_amounts(self):
        """Validate amount fields"""
        if flt(self.outstanding_amount) <= 0:
            frappe.throw(_("Outstanding Amount must be greater than zero"))
        
        if flt(self.allocated_amount) < 0:
            frappe.throw(_("Allocated Amount cannot be negative"))
        
        # Validate against outstanding amount
        if flt(self.allocated_amount) > flt(self.outstanding_amount):
            frappe.throw(
                _("Allocated amount ({0}) cannot exceed outstanding amount ({1})").format(
                    self.allocated_amount, self.outstanding_amount
                )
            )
    
    def auto_fetch_member_name(self):
        """Auto-fetch member name"""
        if self.member and not self.member_name:
            member_doc = frappe.get_doc("SHG Member", self.member)
            self.member_name = member_doc.member_name
    
    def before_save(self):
        """Update processing status based on allocation amount"""
        if flt(self.allocated_amount) > 0 and self.processing_status == "Pending":
            self.processing_status = "Processing"
        elif flt(self.allocated_amount) == 0 and self.processing_status in ["Processing", "Processed"]:
            self.processing_status = "Pending"
            self.is_processed = 0
            self.payment_entry = None
            self.processed_date = None


# Helper function for float conversion
def flt(amount, precision=2):
    """Convert to float with precision"""
    if amount is None:
        return 0.0
    return round(float(amount), precision)