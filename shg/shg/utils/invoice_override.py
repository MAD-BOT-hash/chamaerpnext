import frappe
from frappe.utils import getdate, today

def allow_backdated_invoices(doc, method=None):
    """
    Allow backdated invoices by skipping date validation when the setting is enabled.
    This function is called via doc_events hook before_validate for all doctypes.
    """
    # Check if this is an SHG Contribution Invoice
    if doc.doctype == "SHG Contribution Invoice":
        # Check if historical backdated invoices are allowed
        allow_historical = frappe.db.get_single_value("SHG Settings", "allow_historical_backdated_invoices") or 0
        
        # If historical backdated invoices are allowed, skip date validation
        if allow_historical:
            # For backdated invoices, set due_date same as invoice_date to prevent ERPNext validation errors
            if doc.supplier_invoice_date or (doc.invoice_date and getdate(doc.invoice_date) != getdate(today())):
                doc.due_date = doc.invoice_date