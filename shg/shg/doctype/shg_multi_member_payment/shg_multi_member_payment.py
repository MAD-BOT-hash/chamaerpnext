import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from shg.shg.utils.company_utils import get_default_company

class SHGMultiMemberPayment(Document):
    def before_validate(self):
        """Auto-set company from SHG Settings and handle naming_series"""
        # Handle naming_series for backward compatibility
        if not getattr(self, "naming_series", None):
            self.naming_series = "SHG-MMP-.YYYY.-"
        
        self.company = self.company or get_default_company()
        
        # Auto-calculate total payment amount
        total = 0.0
        if self.invoices:
            for row in self.invoices:
                total += flt(row.payment_amount or 0)
        self.total_payment_amount = total
    
    def validate(self):
        """Validate bulk payment"""
        # Skip validation during dialog operations
        if getattr(self, "__during_dialog_operation", False):
            return
            
        # Validate total_payment_amount > 0
        if flt(self.total_payment_amount) <= 0:
            frappe.throw(_("Total payment amount must be greater than zero"))
            
        # Validate required fields in child table
        for row in self.invoices:
            if not row.reference_doctype:
                frappe.throw(_("Row {0}: Reference Doctype is required").format(row.idx))
            if not row.reference_name:
                frappe.throw(_("Row {0}: Reference Name is required").format(row.idx))
            if not row.payment_amount or flt(row.payment_amount) <= 0:
                frappe.throw(_("Row {0}: Payment Amount must be greater than zero").format(row.idx))
            if not row.outstanding_amount or row.outstanding_amount < 0:
                frappe.throw(_("Row {0}: Outstanding amount is missing or invalid").format(row.idx))
            if row.payment_amount > row.outstanding_amount:
                frappe.throw(_("Row {0}: Payment amount cannot exceed outstanding amount").format(row.idx))
            
        # Run all validation checks
        self.validate_no_closed_documents()
        self.validate_no_fully_paid_documents()
        self.validate_no_duplicate_across_batches()
        self.validate_payment_amount_vs_outstanding()
        self.validate_totals()
    
    def validate_no_closed_documents(self):
        """Validate that no closed documents are included"""
        for row in self.invoices:
            if row.reference_doctype and row.reference_name:
                # Check if document is closed
                if frappe.db.has_column(row.reference_doctype, "is_closed"):
                    is_closed = frappe.db.get_value(row.reference_doctype, row.reference_name, "is_closed")
                    if is_closed:
                        frappe.logger().info(f"[SHG] Blocked payment for closed document {row.reference_name}")
                        frappe.throw(_("Document {0} is closed and cannot be processed again.").format(row.reference_name))
    
    def validate_no_fully_paid_documents(self):
        """Validate that no fully paid documents are included"""
        for row in self.invoices:
            if row.reference_doctype and row.reference_name:
                # Check if document is fully paid
                status = frappe.db.get_value(row.reference_doctype, row.reference_name, "status")
                if status == "Paid":
                    frappe.logger().info(f"[SHG] Blocked payment for Paid document {row.reference_name}")
                    frappe.throw(_("Document {0} is already Paid and cannot be included in a new payment batch.").format(row.reference_name))
    
    def validate_no_duplicate_across_batches(self):
        """Validate that documents are not processed in another submitted payment batch"""
        for row in self.invoices:
            if row.reference_doctype and row.reference_name:
                # Check if document is already processed in another submitted payment batch
                existing_payments = frappe.db.sql("""
                    SELECT parent
                    FROM `tabSHG Multi Member Payment Invoice`
                    WHERE reference_doctype = %s AND reference_name = %s AND parent != %s
                """, (row.reference_doctype, row.reference_name, self.name))
                
                for payment in existing_payments:
                    payment_docstatus = frappe.db.get_value("SHG Multi Member Payment", payment[0], "docstatus")
                    if payment_docstatus == 1:  # Submitted
                        frappe.logger().info(f"[SHG] Blocked payment for document {row.reference_name} already in payment {payment[0]}")
                        frappe.throw(_("Document {0} is already processed in another submitted payment batch {1}.").format(row.reference_name, payment[0]))
    
    def validate_payment_amount_vs_outstanding(self):
        """Validate that payment amounts do not exceed outstanding amounts"""
        from shg.shg.utils.payment_utils import get_outstanding
        for row in self.invoices:
            if row.reference_doctype and row.reference_name and row.payment_amount:
                outstanding = get_outstanding(row.reference_doctype, row.reference_name)
                if flt(row.payment_amount) > outstanding:
                    frappe.throw(_("Document {0} has only {1} outstanding, cannot allocate {2}").format(
                        row.reference_name, outstanding, row.payment_amount))
    
    def validate_totals(self):
        """Validate and compute totals"""
        total_outstanding = 0.0
        total_payment = 0.0
        total_documents = 0
        
        from shg.shg.utils.payment_utils import get_outstanding
        for row in self.invoices:
            if row.reference_doctype and row.reference_name:
                outstanding = get_outstanding(row.reference_doctype, row.reference_name)
                total_outstanding += outstanding
                total_payment += flt(row.payment_amount or 0)
                total_documents += 1
        
        self.total_outstanding_before = total_outstanding
        self.total_payment_amount = total_payment
        self.total_remaining_after = total_outstanding - total_payment
        self.total_documents_selected = total_documents
        
        # Generate payment summary
        self.payment_summary = _("""{0} documents selected
Total outstanding: {1}
Paid now: {2}
Remaining after payment: {3}""").format(
            total_documents,
            self.total_outstanding_before,
            self.total_payment_amount,
            self.total_remaining_after
        )
    
    def on_submit(self):
        """Process bulk payment"""
        from shg.shg.utils.payment_utils import process_bulk_payment
        process_bulk_payment(self.name)
        
        # Update display fields
        self.update_display_fields()
    
    def on_cancel(self):
        """Cancel Payment Entry & reverse statuses"""
        # Note: In a real implementation, you would need to implement cancel functionality
        # For now, we'll just update the status
        self.db_set("payment_status", "Cancelled")
    
    @frappe.whitelist()
    def fetch_unpaid_items(self):
        """Fetch unpaid items for bulk payment"""
        if not self.member:
            frappe.throw(_("Please select a Member before fetching unpaid documents."))
        
        from shg.shg.utils.payment_utils import get_all_unpaid
        return get_all_unpaid(self.member)
    
    @frappe.whitelist()
    def fetch_unpaid_invoices(self):
        """Fetch unpaid contribution invoices"""
        if not self.member:
            frappe.throw(_("Please select a Member before fetching unpaid documents."))
            
        from shg.shg.utils.payment_utils import get_unpaid_invoices
        return get_unpaid_invoices(self.member)
    
    @frappe.whitelist()
    def fetch_unpaid_contributions(self):
        """Fetch unpaid contributions"""
        if not self.member:
            frappe.throw(_("Please select a Member before fetching unpaid documents."))
            
        from shg.shg.utils.payment_utils import get_unpaid_contributions
        return get_unpaid_contributions(self.member)
    
    @frappe.whitelist()
    def fetch_unpaid_fines(self):
        """Fetch unpaid meeting fines"""
        if not self.member:
            frappe.throw(_("Please select a Member before fetching unpaid documents."))
            
        from shg.shg.utils.payment_utils import get_unpaid_fines
        return get_unpaid_fines(self.member)
    
    @frappe.whitelist()
    def fetch_all_unpaid(self):
        """Fetch all unpaid items"""
        if not self.member:
            frappe.throw(_("Please select a Member before fetching unpaid documents."))
            
        from shg.shg.utils.payment_utils import get_all_unpaid
        return get_all_unpaid(self.member)
    
    @frappe.whitelist()
    def recalculate_totals(self):
        """Recalculate totals"""
        total_outstanding = 0.0
        total_payment = 0.0
        total_documents = 0
        
        from shg.shg.utils.payment_utils import get_outstanding
        # Loop through invoices child table
        for row in self.invoices:
            if row.reference_doctype and row.reference_name:
                outstanding = get_outstanding(row.reference_doctype, row.reference_name)
                total_outstanding += outstanding
                total_payment += flt(row.payment_amount or 0)
                total_documents += 1
        
        # Update parent fields
        self.total_outstanding_before = total_outstanding
        self.total_payment_amount = total_payment
        self.total_remaining_after = total_outstanding - total_payment
        self.total_documents_selected = total_documents
        
        # Save the doc
        self.save(ignore_permissions=True)
        
        # Return updated numbers as dict
        return {
            "total_outstanding_before": self.total_outstanding_before,
            "total_payment_amount": self.total_payment_amount,
            "total_remaining_after": self.total_remaining_after,
            "total_documents_selected": self.total_documents_selected
        }
    
    def update_display_fields(self):
        """Update display fields after submission"""
        # Set payment status
        if self.total_remaining_after <= 0:
            self.db_set("payment_status", "Paid")
        elif self.total_payment_amount > 0:
            self.db_set("payment_status", "Partially Paid")
        else:
            self.db_set("payment_status", "Unpaid")
        
        # Set posted to GL flag (simplified)
        self.db_set("posted_to_gl", 1 if self.payment_entry else 0)