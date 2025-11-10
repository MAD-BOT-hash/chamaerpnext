import frappe
from frappe.utils import nowdate, flt

def ensure_payment_entry_exists(repayment_doc):
    loan_name = repayment_doc.loan
    loan = frappe.get_doc("SHG Loan", loan_name)
    company = loan.company or frappe.defaults.get_user_default("Company")
    member = loan.member

    # check if still valid
    if repayment_doc.payment_entry and frappe.db.exists("SHG Payment Entry", repayment_doc.payment_entry):
        return repayment_doc.payment_entry

    frappe.msgprint(f"🔄 Auto-creating Payment Entry for Repayment {repayment_doc.name}")

    # ---- Default accounts (replace with your own or pull from config)
    cash_account = frappe.db.get_value("Company", company, "default_cash_account") \
                   or frappe.db.get_value("Account", {"account_name": "Cash", "company": company}, "name")
    receivable_account = frappe.db.get_value("Account", {"account_name": "SHG Loans Receivable", "company": company}, "name")

    if not cash_account or not receivable_account:
        frappe.throw(f"Missing default accounts for company {company}. "
                     "Please set Cash/Receivable accounts in SHG configuration or Company defaults.")

    # ---- Build Payment Entry
    pe = frappe.new_doc("SHG Payment Entry")  # or "Payment Entry" if using core
    pe.payment_type = "Receive"
    pe.company = company
    pe.party_type = "Customer"
    pe.party = member
    pe.paid_amount = flt(repayment_doc.total_paid)
    pe.received_amount = flt(repayment_doc.total_paid)
    pe.mode_of_payment = "Cash"
    pe.reference_no = repayment_doc.name
    pe.reference_date = repayment_doc.posting_date or nowdate()
    pe.remarks = f"Auto-generated for SHG Loan {loan_name} via Repayment {repayment_doc.name}"

    # --- 🔑 Set mandatory accounts
    pe.paid_from = receivable_account       # The asset account being reduced
    pe.paid_to = cash_account               # The cash/bank account being increased

    # optional reference
    try:
        pe.append("references", {
            "reference_doctype": "SHG Loan",
            "reference_name": loan_name,
            "allocated_amount": flt(repayment_doc.total_paid)
        })
    except Exception:
        frappe.log_error("Reference not allowed on Payment Entry", loan_name)

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
               OR payment_entry NOT IN (SELECT name FROM `tabSHG Payment Entry`))
    """, (pe.name, loan_name))
    frappe.db.commit()

    frappe.msgprint(f"✅ Payment Entry {pe.name} created and linked to {repayment_doc.name}")
    return pe.name