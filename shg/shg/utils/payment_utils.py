import frappe
from frappe import _
from frappe.utils import flt, nowdate, today

def resolve_company_for_invoice(invoice):
    """
    Resolve company reliably for ANY SHG invoice-like document.
    Order of resolution:
    1. If invoice.company exists → use it
    2. If member receivable account exists → use account's company
    3. Fallback to SHG Settings default company
    4. Throw clear error if still missing
    """

    # 1) Direct company on invoice (if field exists)
    inv_company = getattr(invoice, "company", None)
    if inv_company:
        return inv_company

    # 2) Infer from member receivable ledger
    try:
        from shg.shg.utils.account_helpers import get_or_create_member_receivable
        member_account = get_or_create_member_receivable(invoice.member, None)
        acc_company = frappe.db.get_value("Account", member_account, "company")
        if acc_company:
            return acc_company
    except Exception:
        pass

    # 3) Fallback to SHG Settings
    settings_company = frappe.db.get_single_value("SHG Settings", "company")
    if settings_company:
        return settings_company

    # 4) Still missing → throw clean error
    frappe.throw(
        f"Company cannot be resolved for invoice {invoice.name}. "
        "Please set 'Company' in SHG Settings."
    )

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
def receive_multiple_payments(invoices, payment_date=None, payment_method=None, account=None):
    """
    Receive payments for multiple contribution invoices.
    
    Args:
        invoices (list): List of invoice dictionaries with 'name' and optionally 'paid_amount'
        payment_date (str): Payment date (defaults to today)
        payment_method (str): Payment method (defaults to 'Cash')
        account (str): Account to credit (defaults to Cash account)
        
    Returns:
        dict: Result with processed count
    """
    processed = 0
    payment_date = payment_date or today()
    payment_method = payment_method or "Cash"
    
    for entry in invoices:
        if not isinstance(entry, dict) or "name" not in entry:
            frappe.log_error(str(entry), "Invalid invoice entry in receive_multiple_payments")
            continue

        invoice = frappe.get_doc("SHG Contribution Invoice", entry["name"])
        
        # For SHGContributionInvoice, calculate paid_amount based on the entry or assume full payment
        # SHGContributionInvoice doesn't have a paid_amount field, so we need to calculate it
        if "paid_amount" in entry:
            paid_amount = flt(entry.get("paid_amount"))
        else:
            # If no paid_amount specified, check if there's a linked Sales Invoice to determine outstanding amount
            if invoice.sales_invoice:
                sales_invoice = frappe.get_doc("Sales Invoice", invoice.sales_invoice)
                # For partial payment scenarios, we'll use half the amount as an example
                # In real implementation, this should be calculated properly based on business logic
                paid_amount = flt(sales_invoice.outstanding_amount or invoice.amount)
            else:
                # If no Sales Invoice, assume full payment
                paid_amount = flt(invoice.amount)

        if paid_amount <= 0:
            continue

        # --- Create a Payment Entry safely ---
        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive"
        pe.party_type = "Customer"
        pe.party = invoice.member
        pe.posting_date = payment_date
        pe.mode_of_payment = payment_method
        
        # Resolve company using the universal resolver
        company = resolve_company_for_invoice(invoice)
        pe.company = company

        # --- Credit side ---
        # Get cash or bank account for the company
        cash_or_bank = frappe.db.get_single_value("SHG Settings", "default_bank_account")
        if not cash_or_bank:
            # Fallback to cash account
            cash_or_bank = frappe.db.get_single_value("SHG Settings", "default_cash_account")
        if not cash_or_bank:
            # Last resort - try to find any bank or cash account for the company
            cash_or_bank_accounts = frappe.get_all("Account", 
                filters={"company": company, "account_type": ["in", ["Bank", "Cash"]], "is_group": 0},
                limit=1)
            if cash_or_bank_accounts:
                cash_or_bank = cash_or_bank_accounts[0].name
        if not cash_or_bank:
            frappe.throw("No bank or cash account found for company {0}".format(company))
            
        pe.append("accounts", {
            "account": cash_or_bank,
            "credit_in_account_currency": paid_amount
        })

        # --- Debit side ---
        from shg.shg.utils.account_helpers import get_or_create_member_receivable
        member_account = get_or_create_member_receivable(invoice.member, company)
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
        # Calculate the new status based on payment
        if invoice.sales_invoice:
            sales_invoice = frappe.get_doc("Sales Invoice", invoice.sales_invoice)
            new_outstanding = sales_invoice.outstanding_amount - paid_amount
            if new_outstanding <= 0:
                invoice.db_set("status", "Paid")
            else:
                invoice.db_set("status", "Partially Paid")
        else:
            # For invoices without Sales Invoice, determine status based on payment amount
            if paid_amount >= flt(invoice.amount):
                invoice.db_set("status", "Paid")
            else:
                invoice.db_set("status", "Partially Paid")
                
        contribution_name = frappe.db.get_value("SHG Contribution", {"invoice_reference": invoice.name}, "name")
        if contribution_name:
            contrib = frappe.get_doc("SHG Contribution", contribution_name)
            contrib.update_payment_status(paid_amount)

        processed += 1

    frappe.msgprint(f"Successfully processed {processed} payment(s).")
    return {"processed": processed}