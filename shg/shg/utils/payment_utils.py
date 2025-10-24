import frappe
from frappe import _
from frappe.utils import flt, nowdate
import json

@frappe.whitelist()
def get_unpaid_invoices(member=None):
    """
    Get unpaid invoices for a member or all members.
    
    Args:
        member (str, optional): Member ID to filter by
        
    Returns:
        list: List of unpaid invoices
    """
    filters = {
        "status": ["in", ["Unpaid", "Partially Paid"]],
        "docstatus": 1
    }
    
    if member:
        filters["member"] = member
        
    invoices = frappe.get_all(
        "SHG Contribution Invoice",
        filters=filters,
        fields=["name", "member", "member_name", "invoice_date", "due_date", "amount", "status"]
    )
    
    # Add outstanding amount calculation
    for invoice in invoices:
        # For now, we'll use the full amount as outstanding
        # In a real implementation, this would need to account for partial payments
        invoice["unpaid_amount"] = invoice["amount"] or 0
        
    return invoices

@frappe.whitelist()
def receive_multiple_payments(selected_invoices, payment_date=None, payment_method=None, account=None):
    """
    Process multiple invoice payments safely with proper JSON and dict handling.
    """
    import json
    # Already imported at the top

    # --- Parse and validate JSON input ---
    invoices = []
    try:
        invoices = json.loads(selected_invoices)
        if isinstance(invoices, dict):
            invoices = [invoices]
        if not isinstance(invoices, list):
            frappe.throw("Invalid format: selected_invoices must be a list of dicts.")
    except Exception as e:
        frappe.throw(f"Invalid JSON data for selected_invoices: {e}")

    processed = 0
    payment_date = payment_date or nowdate()
    payment_method = payment_method or "Cash"
    account = account or frappe.db.get_value("Account", {"account_type": "Cash", "is_group": 0}, "name")

    for entry in invoices:
        if not isinstance(entry, dict) or "name" not in entry:
            frappe.log_error(str(entry), "Invalid invoice entry in receive_multiple_payments")
            continue

        invoice = frappe.get_doc("SHG Contribution Invoice", entry["name"])
        paid_amount = flt(entry.get("paid_amount", invoice.amount or 0))

        if paid_amount <= 0:
            continue

        # --- Create a Payment Entry safely ---
        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive"
        pe.party_type = "Customer"
        pe.party = invoice.member
        pe.posting_date = payment_date
        pe.mode_of_payment = payment_method
        pe.company = invoice.company or frappe.defaults.get_global_default("company")

        # --- Credit side ---
        pe.append("accounts", {
            "account": account,
            "credit_in_account_currency": paid_amount
        })

        # --- Debit side ---
        from shg.shg.utils.account_utils import get_or_create_member_account
        member = frappe.get_doc("SHG Member", invoice.member)
        member_account = get_or_create_member_account(member, pe.company)
        if not member_account:
            frappe.throw(f"Unable to find ledger account for member {invoice.member}")

        pe.append("accounts", {
            "account": member_account,
            "debit_in_account_currency": paid_amount,
            "reference_type": "SHG Contribution Invoice",
            "reference_name": invoice.name
        })

        pe.insert(ignore_permissions=True)
        pe.submit()

        # --- Update invoice & contribution record ---
        invoice.db_set("status", "Paid" if paid_amount >= flt(invoice.amount) else "Partially Paid")
        contribution_name = frappe.db.get_value("SHG Contribution", {"invoice_reference": invoice.name}, "name")
        if contribution_name:
            contrib = frappe.get_doc("SHG Contribution", contribution_name)
            contrib.update_payment_status(paid_amount)

        processed += 1

    frappe.msgprint(f"Successfully processed {processed} payment(s).")
    return {"processed": processed}