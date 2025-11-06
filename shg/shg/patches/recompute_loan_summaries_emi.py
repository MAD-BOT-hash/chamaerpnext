import frappe
from shg.shg.loan_utils import update_loan_summary, compute_totals

def execute():
    loans = frappe.get_all("SHG Loan", filters={"docstatus": ["!=", 2]}, pluck="name")
    for ln in loans:
        # Normalize schedule rows (ensure remaining_amount filled)
        rows = frappe.get_all("SHG Loan Repayment Schedule", filters={"parent": ln},
                              fields=["name", "total_payment", "amount_paid", "remaining_amount", "status"])
        for r in rows:
            amount_paid = float(r.get("amount_paid") or 0)
            total = float(r.get("total_payment") or 0)
            remaining = total - amount_paid
            status = "Paid" if remaining <= 0.00001 else ("Partially Paid" if amount_paid > 0 else "Unpaid")
            frappe.db.set_value("SHG Loan Repayment Schedule", r["name"], {
                "remaining_amount": max(remaining, 0),
                "status": status
            }, update_modified=False)

        update_loan_summary(ln)