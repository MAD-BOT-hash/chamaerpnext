import frappe
from frappe.utils import flt

def _compute_summary(loan_doc):
    """Return summary values computed from repayment_schedule or standalone schedule."""
    fields = ["due_date", "total_payment", "amount_paid", "unpaid_balance", "status"]
    summary = {"total_payable": 0, "total_repaid": 0, "balance_amount": 0, "overdue_amount": 0}

    # Try child table first
    rows = loan_doc.get("repayment_schedule") or []

    # If rows are empty, fallback to standalone child DocType
    if not rows and frappe.db.table_exists("SHG Loan Repayment Schedule"):
        rows = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={"parent": loan_doc.name},
            fields=fields,
            order_by="due_date asc",
        )

    # If still no rows, return zeroes
    if not rows:
        return summary

    # Aggregate summary values
    for r in rows:
        summary["total_payable"] += flt(r.get("total_payment", 0))
        summary["total_repaid"] += flt(r.get("amount_paid", 0))
        summary["balance_amount"] += flt(r.get("unpaid_balance", 0))
        if r.get("status") == "Overdue":
            summary["overdue_amount"] += flt(r.get("unpaid_balance", 0))

    return summary

def execute():
    """
    Patch to fix repayment summary computation and sync existing loans.
    """
    print("Updating repayment summary logic and backfilling existing loans...")

    # Get all submitted or disbursed loans
    loans = frappe.get_all("SHG Loan", filters={"docstatus": ["<=", 1]}, pluck="name")

    for loan_name in loans:
        loan = frappe.get_doc("SHG Loan", loan_name)

        # Compute summary
        summary = _compute_summary(loan)

        # Update relevant fields
        loan.db_set("total_payable", summary["total_payable"])
        loan.db_set("total_repaid", summary["total_repaid"])
        loan.db_set("balance_amount", summary["balance_amount"])
        loan.db_set("overdue_amount", summary["overdue_amount"])

        print(f"Updated summary for {loan_name}")

    print("✅ Done — repayment summaries have been synced.")