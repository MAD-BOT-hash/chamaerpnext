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
    
    Args:
        selected_invoices (str): JSON string of selected invoices with payment amounts
        payment_date (str, optional): Payment date. Defaults to today.
        payment_method (str, optional): Payment method. Defaults to "Cash".
        account (str, optional): Receiving account. Defaults to default cash account.
    
    Returns:
        dict: Result with number of processed payments
    """
    # --- Parse and validate JSON input ---
    invoices = []
    try:
        invoices = json.loads(selected_invoices)
        # Handle case where a single dict is passed instead of a list
        if isinstance(invoices, dict):
            invoices = [invoices]
        if not isinstance(invoices, list):
            frappe.throw(_("Invalid format: selected_invoices must be a list of dicts."))
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "JSON Parse Error in receive_multiple_payments")
        frappe.throw(_("Invalid JSON data for selected_invoices: {0}").format(str(e)))

    processed = 0
    payment_date = payment_date or nowdate()
    payment_method = payment_method or "Cash"
    
    # Get default account if not provided
    if not account:
        account = frappe.db.get_value("Account", {"account_type": "Cash", "is_group": 0}, "name")
        if not account:
            # Fallback to bank account
            account = frappe.db.get_value("Account", {"account_type": "Bank", "is_group": 0}, "name")
        if not account:
            frappe.throw(_("Unable to find a default Cash or Bank account. Please provide an account."))

    company = frappe.defaults.get_global_default("company")
    
    for entry in invoices:
        try:
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
            pe.company = company or invoice.company or frappe.defaults.get_global_default("company")
            pe.paid_amount = paid_amount
            pe.received_amount = paid_amount

            # --- Credit side (Bank/Cash account) ---
            pe.append("accounts", {
                "account": account,
                "debit_in_account_currency": paid_amount
            })

            # --- Debit side (Member account) ---
            from shg.shg.utils.account_utils import get_or_create_member_account
            member = frappe.get_doc("SHG Member", invoice.member)
            member_account = get_or_create_member_account(member, pe.company)
            
            if not member_account:
                frappe.throw(_("Unable to find ledger account for member {0}").format(invoice.member))

            pe.append("accounts", {
                "account": member_account,
                "credit_in_account_currency": paid_amount,
                "reference_type": "SHG Contribution Invoice",
                "reference_name": invoice.name
            })

            pe.insert(ignore_permissions=True)
            pe.submit()

            # --- Update invoice & contribution record ---
            invoice.db_set("status", "Paid" if paid_amount >= flt(invoice.amount) else "Partially Paid")
            
            # Update linked contribution if exists
            contribution_name = frappe.db.get_value("SHG Contribution", {"invoice_reference": invoice.name}, "name")
            if contribution_name:
                try:
                    contrib = frappe.get_doc("SHG Contribution", contribution_name)
                    contrib.update_payment_status(paid_amount)
                except Exception as e:
                    frappe.log_error(frappe.get_traceback(), f"Error updating contribution {contribution_name}")

            processed += 1
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Error processing invoice {entry.get('name', 'Unknown')}")
            continue

    frappe.msgprint(_("Successfully processed {0} payment(s).").format(processed))
    return {"processed": processed}