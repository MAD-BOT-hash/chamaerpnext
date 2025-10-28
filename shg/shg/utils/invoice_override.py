import frappe
from frappe.utils import getdate

def allow_backdated_invoices(doc, method):
    """
    Allow historical invoices by overriding ERPNext's due_date < posting_date validation.
    Works for both ERPNext and SHG Contribution Invoices.
    """

    from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice

    def custom_validate_due_date(self):
        """Override default validate_due_date to allow historical or backdated invoices."""
        # Ensure both dates are datetime.date objects
        if not self.due_date:
            self.due_date = self.posting_date

        due_date = getdate(self.due_date)
        posting_date = getdate(self.posting_date)

        # Allow due_date < posting_date instead of throwing error
        if due_date < posting_date:
            frappe.logger().info(
                f"[SHG Override] Allowed backdated invoice: {self.name} "
                f"due_date={due_date}, posting_date={posting_date}"
            )

    # Patch only once per worker
    if not hasattr(SalesInvoice.validate_due_date, '_is_shg_override'):
        SalesInvoice.validate_due_date = custom_validate_due_date
        setattr(SalesInvoice.validate_due_date, '_is_shg_override', True)

    # Also extend for SHG Contribution Invoice if applicable
    try:
        from shg.shg.doctype.shg_contribution_invoice.shg_contribution_invoice import SHGContributionInvoice

        if hasattr(SHGContributionInvoice, "validate_due_date"):
            SHGContributionInvoice.validate_due_date = custom_validate_due_date
            setattr(SHGContributionInvoice.validate_due_date, '_is_shg_override', True)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG Backdate Override Patch Failed")