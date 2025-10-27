import frappe
from frappe.model.document import Document

def allow_backdated_invoices():
    """
    Removes ERPNext validation that prevents due_date < posting_date,
    allowing SHG or historical back-entries.
    This should be called via hooks or monkey-patching.
    """
    from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice

    def custom_validate_due_date(self):
        """
        Override default validate_due_date to allow historical invoices.
        """
        if not self.due_date:
            self.due_date = self.posting_date

        # Skip the 'due date < posting date' check entirely
        # Just log a warning if it's reversed for audit purposes.
        if self.due_date < self.posting_date:
            frappe.logger().info(
                f"[SHG Override] Allowed backdated invoice: {self.name} "
                f"due_date={self.due_date}, posting_date={self.posting_date}"
            )

    # Patch ERPNext core method
    SalesInvoice.validate_due_date = custom_validate_due_date