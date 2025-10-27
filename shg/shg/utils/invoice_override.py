import frappe

def allow_backdated_invoices(doc, method):
    """
    Allow historical invoices by overriding ERPNext's due_date < posting_date validation.
    """
    # Only apply to Sales Invoice documents
    if doc.doctype != "Sales Invoice":
        return
        
    from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice

    def custom_validate_due_date(self):
        """Override default validate_due_date to allow historical invoices."""
        if not self.due_date:
            self.due_date = self.posting_date

        # Allow backdated invoices instead of throwing an error
        if self.due_date < self.posting_date:
            frappe.logger().info(
                f"[SHG Override] Allowed backdated invoice: {self.name} "
                f"due_date={self.due_date}, posting_date={self.posting_date}"
            )

    # Patch only once per worker
    if not hasattr(SalesInvoice, '_shg_override_applied'):
        SalesInvoice.validate_due_date = custom_validate_due_date
        SalesInvoice._shg_override_applied = True