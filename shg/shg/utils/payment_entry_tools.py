import frappe
from frappe.utils import nowdate, flt

def ensure_payment_entry_exists(repayment_doc):
    """Ensure the SHG Loan Repayment has a valid Payment Entry.
       If missing or deleted, recreate one and link it back."""

    loan_name = repayment_doc.loan
    loan = frappe.get_doc("SHG Loan", loan_name)
    member = loan.member
    company = loan.company or frappe.defaults.get_user_default("Company")

    # check existing link
    if repayment_doc.payment_entry and frappe.db.exists("SHG Payment Entry", repayment_doc.payment_entry):
        return repayment_doc.payment_entry

    frappe.msgprint(f"🔄 Auto-creating Payment Entry for Repayment {repayment_doc.name}")

    pe = frappe.new_doc("SHG Payment Entry")
    pe.payment_type = "Receive"
    pe.company = company
    pe.party_type = "Customer"
    pe.party = member
    pe.mode_of_payment = "Cash"
    pe.paid_amount = flt(repayment_doc.total_paid)
    pe.received_amount = flt(repayment_doc.total_paid)
    pe.reference_no = repayment_doc.name
    pe.reference_date = repayment_doc.posting_date or nowdate()
    pe.remarks = f"Auto-generated for SHG Loan {loan_name} via Repayment {repayment_doc.name}"

    # optional reference row (skip if core Payment Entry rejects SHG Loan)
    try:
        pe.append("references", {
            "reference_doctype": "SHG Loan",
            "reference_name": loan_name,
            "allocated_amount": flt(repayment_doc.total_paid)
        })
    except Exception:
        # silently ignore if not allowed
        frappe.log_error("Reference not allowed on Payment Entry", loan_name)

    pe.insert(ignore_permissions=True)
    pe.submit()

    # link back
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