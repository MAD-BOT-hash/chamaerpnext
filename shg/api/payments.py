import frappe
from frappe import _
from frappe.utils import flt
import json
from shg.shg.utils.account_utils import get_or_create_member_account

@frappe.whitelist()
def receive_multiple_payments(selected_invoices, payment_date, payment_method, account):
    """
    Receive multiple payments for selected SHG Contribution Invoices
    
    Args:
        selected_invoices (str): JSON string of selected invoices with payment amounts
        payment_date (str): Payment date
        payment_method (str): Payment method (Cash, Mpesa, etc.)
        account (str): Receiving account (Cash/Bank account)
    
    Returns:
        str: Success message with number of processed payments
    """
    try:
        selected_invoices = json.loads(selected_invoices)
    except json.JSONDecodeError:
        frappe.throw(_("Invalid invoice data format"))
    
    total_processed = 0
    company = frappe.get_value("Global Defaults", None, "default_company")
    
    for inv in selected_invoices:
        invoice = frappe.get_doc("SHG Contribution Invoice", inv["name"])
        paid_amount = flt(inv.get("paid_amount", 0))
        
        if not paid_amount or paid_amount <= 0:
            continue
            
        # Get member document
        member = frappe.get_doc("SHG Member", invoice.member)
        
        # Get member account (Credit account)
        member_account = get_or_create_member_account(member, company)
        
        # Create Payment Entry
        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive"
        pe.posting_date = payment_date
        pe.party_type = "Customer"
        pe.party = invoice.member
        pe.company = company
        pe.mode_of_payment = payment_method
        pe.paid_amount = paid_amount
        pe.received_amount = paid_amount
        
        # Add reference to the invoice
        pe.append("references", {
            "reference_doctype": "SHG Contribution Invoice",
            "reference_name": invoice.name,
            "allocated_amount": paid_amount
        })
        
        # Add accounts following the accounting rule:
        # Debit to Cash/Bank Account (account parameter) 
        # Credit to Member Ledger Account (member_account)
        pe.append("accounts", {
            "account": account,  # Cash/Bank account (Debit)
            "debit_in_account_currency": paid_amount
        })
        pe.append("accounts", {
            "account": member_account,  # Member account (Credit)
            "credit_in_account_currency": paid_amount
        })
        
        pe.insert(ignore_permissions=True)
        pe.submit()
        
        # Update invoice status
        invoice.db_set("status", "Paid" if paid_amount >= flt(invoice.amount) else "Partially Paid")
        
        # Update linked contribution if exists
        contribution_name = frappe.db.get_value("SHG Contribution", {"invoice_reference": invoice.name}, "name")
        if contribution_name:
            contribution = frappe.get_doc("SHG Contribution", contribution_name)
            contribution.update_payment_status(paid_amount)
            
        total_processed += 1
    
    return f"✅ {total_processed} payments processed successfully."