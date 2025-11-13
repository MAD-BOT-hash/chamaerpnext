import frappe
from frappe.utils import nowdate, flt

def ensure_payment_entry_exists(repayment_doc):
    loan_name = repayment_doc.loan
    loan = frappe.get_doc("SHG Loan", loan_name)
    company = loan.company or frappe.defaults.get_user_default("Company")
    member = loan.member

    # check if still valid
    if repayment_doc.payment_entry and frappe.db.exists("Payment Entry", repayment_doc.payment_entry):
        return repayment_doc.payment_entry

    frappe.msgprint(f"⚠️ Payment Entry {repayment_doc.payment_entry} not found – recreating...")
    return auto_create_payment_entry(repayment_doc)

def auto_create_payment_entry(repayment_doc):
    loan = frappe.get_doc("SHG Loan", repayment_doc.loan)
    company = loan.company
    member = loan.member

    # locate default accounts
    cash_account = frappe.db.get_value("Account",
        {"account_name": "Cash", "company": company}, "name")
    receivable_account = get_or_create_member_receivable(member, company)

    if not cash_account or not receivable_account:
        frappe.throw(f"Missing default Cash/Receivable accounts for {company}")

    pe = frappe.new_doc("Payment Entry")     # Use standard Payment Entry
    pe.payment_type = "Receive"
    pe.company = company
    pe.party_type = "Customer"
    pe.party = member
    pe.paid_from = receivable_account
    pe.paid_to = cash_account
    pe.paid_amount = repayment_doc.total_paid
    pe.received_amount = repayment_doc.total_paid
    pe.mode_of_payment = repayment_doc.payment_method or "Cash"
    pe.reference_no = repayment_doc.name
    pe.reference_date = repayment_doc.posting_date
    pe.remarks = f"Auto-created for SHG Loan {repayment_doc.loan}"

    pe.insert(ignore_permissions=True)
    pe.submit()

    repayment_doc.payment_entry = pe.name
    repayment_doc.save(ignore_permissions=True)
    
    # update repayment schedule rows if they point to old / missing entries
    frappe.db.sql("""
        UPDATE `tabSHG Loan Repayment Schedule`
        SET payment_entry=%s
        WHERE parent=%s
          AND (payment_entry IS NULL
               OR payment_entry=''
               OR payment_entry NOT IN (SELECT name FROM `tabPayment Entry`))
    """, (pe.name, repayment_doc.loan))
    frappe.db.commit()

    frappe.msgprint(f"✅ Payment Entry {pe.name} created and linked to {repayment_doc.name}")
    return pe.name

def get_or_create_member_receivable(member, company):
    """Get or create member receivable account."""
    # Try to get existing member receivable account
    account_name = f"{member} - Receivable"
    account = frappe.db.get_value("Account", 
        {"account_name": account_name, "company": company}, "name")
    
    if account:
        return account
    
    # Get company abbreviation
    company_abbr = frappe.db.get_value("Company", company, "abbr")
    
    # Get parent receivable account
    parent_account = frappe.db.get_value("Account",
        {"account_name": "Member Receivables", "company": company}, "name")
    
    if not parent_account:
        parent_account = frappe.db.get_value("Account",
            {"account_name": "Accounts Receivable", "company": company}, "name")
    
    # Create new member receivable account
    account_doc = frappe.get_doc({
        "doctype": "Account",
        "account_name": account_name,
        "account_type": "Receivable",
        "company": company,
        "parent_account": parent_account,
        "account_currency": frappe.db.get_value("Company", company, "default_currency"),
        "is_group": 0
    })
    
    account_doc.insert(ignore_permissions=True)
    return account_doc.name