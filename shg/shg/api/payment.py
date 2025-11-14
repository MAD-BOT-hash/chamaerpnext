import frappe
from frappe import _
from shg.shg.doctype.shg_payment.shg_payment import shg_receive_single_payment, shg_receive_bulk_payment


@frappe.whitelist()
def receive_single_payment(document_type, document_name, amount, mode_of_payment, posting_date=None, reference_no=None):
    """
    API endpoint for receiving payment for a single document
    """
    try:
        result = shg_receive_single_payment(document_type, document_name, amount, mode_of_payment, posting_date, reference_no)
        return result
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "API - Receive Single Payment Failed")
        frappe.throw(_("Failed to process payment: {0}").format(str(e)))


@frappe.whitelist()
def receive_bulk_payment(member, documents, amount, mode_of_payment, posting_date=None, reference_no=None):
    """
    API endpoint for receiving payment for multiple documents
    """
    try:
        result = shg_receive_bulk_payment(member, documents, amount, mode_of_payment, posting_date, reference_no)
        return result
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "API - Receive Bulk Payment Failed")
        frappe.throw(_("Failed to process bulk payment: {0}").format(str(e)))


@frappe.whitelist()
def get_unpaid_invoices(member):
    """
    Get all unpaid invoices for a member (Contribution Invoices + Meeting Fines)
    """
    try:
        # Get unpaid contribution invoices
        contribution_invoices = frappe.get_all(
            "SHG Contribution Invoice",
            filters={
                "member": member,
                "status": ["in", ["Unpaid", "Partially Paid"]],
                "docstatus": 1
            },
            fields=["name", "member", "member_name", "invoice_date", "due_date", "amount", "status"]
        )
        
        # Get unpaid meeting fines
        meeting_fines = frappe.get_all(
            "SHG Meeting Fine",
            filters={
                "member": member,
                "status": "Unpaid",
                "docstatus": 1
            },
            fields=["name", "member", "member_name", "fine_date", "amount", "description", "status"]
        )
        
        # Format contribution invoices
        for inv in contribution_invoices:
            inv.doctype = "SHG Contribution Invoice"
            inv.date = inv.invoice_date
            inv.description = _("Contribution Invoice")
            
        # Format meeting fines
        for fine in meeting_fines:
            fine.doctype = "SHG Meeting Fine"
            fine.date = fine.fine_date
            fine.description = fine.description or _("Meeting Fine")
            
        # Combine and return
        all_unpaid = contribution_invoices + meeting_fines
        
        return all_unpaid
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "API - Get Unpaid Invoices Failed")
        frappe.throw(_("Failed to fetch unpaid invoices: {0}").format(str(e)))