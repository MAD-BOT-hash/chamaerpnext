# shg/shg/api/repayment_refresh.py
import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

SCHEDULE_DT = "SHG Loan Repayment Schedule"
LOAN_DT = "SHG Loan"


def _get_schedule_rows(loan_name: str):
    """Fetch ordered schedule rows for a loan from child table."""
    return frappe.get_all(
        SCHEDULE_DT,
        filters={"parent": loan_name, "parenttype": LOAN_DT},
        fields=[
            "name",
            "due_date",
            "total_payment",
            "amount_paid",
            "unpaid_balance",
            "status",
            "loan_balance",
            "actual_payment_date",
            "payment_date",
        ],
        order_by="due_date asc, idx asc",
        limit_page_length=5000,
    )


def _compute_from_schedule(loan_doc) -> dict:
    """Compute totals purely from SHG Loan Repayment Schedule child rows."""
    rows = _get_schedule_rows(loan_doc.name)
    if not rows:
        return {
            "total_repaid": 0.0,
            "balance_amount": flt(loan_doc.loan_amount or 0),
            "overdue_amount": 0.0,
            "next_due_date": None,
            "last_repayment_date": None,
        }

    today = getdate(nowdate())
    total_repaid = 0.0
    overdue_amount = 0.0
    next_due_date = None
    last_payment_date = None
    last_row_balance = None

    for r in rows:
        total_repaid += flt(r.get("amount_paid") or 0)

        # Latest payment date seen
        apd = r.get("actual_payment_date") or r.get("payment_date")
        if apd:
            apd = getdate(apd)
            if not last_payment_date or apd > last_payment_date:
                last_payment_date = apd

        # Overdue = only rows whose due_date is past and still have unpaid_balance
        due = r.get("due_date")
        unpaid = flt(r.get("unpaid_balance") or 0)
        if due and getdate(due) < today and unpaid > 0:
            overdue_amount += unpaid

        # Next due = first future/present installment with unpaid > 0
        if unpaid > 0:
            if due:
                due_d = getdate(due)
                if (due_d >= today) and (not next_due_date or due_d < next_due_date):
                    next_due_date = due_d

        # Balance preference: use last non-null loan_balance; fallback later
        lb = r.get("loan_balance")
        if lb is not None:
            last_row_balance = flt(lb)

    # Compute balance
    if last_row_balance is not None:
        balance_amount = last_row_balance
    else:
        # Fallback: principal-ish balance = (sum of total_payment) - total_repaid.
        # This is a generic fallback when loan_balance isn't tracked per row.
        total_scheduled = sum(flt(x.get("total_payment") or 0) for x in rows)
        balance_amount = max(0.0, flt(total_scheduled) - flt(total_repaid))

    return {
        "total_repaid": flt(total_repaid),
        "balance_amount": flt(balance_amount),
        "overdue_amount": flt(overdue_amount),
        "next_due_date": next_due_date,
        "last_repayment_date": last_payment_date,
    }


def _apply_to_loan(loan_doc, summary: dict):
    """Persist computed fields onto the SHG Loan safely (incl. submitted loans)."""
    # Allow updates after submit for these specific fields
    loan_doc.flags.ignore_validate_update_after_submit = True

    updates = {
        "total_repaid": summary["total_repaid"],
        "balance_amount": summary["balance_amount"],
        "overdue_amount": summary["overdue_amount"],
        "next_due_date": summary["next_due_date"],
        "last_repayment_date": summary["last_repayment_date"],
    }

    # db_set is efficient and avoids triggering full save cascades
    for field, value in updates.items():
        loan_doc.db_set(field, value, update_modified=True)

    # Optional: small indicator in the timeline
    frappe.msgprint(
        _("Repayment summary refreshed: "
          "Repaid Sh {repaid:,.2f}, Balance Sh {bal:,.2f}, Overdue Sh {od:,.2f}").format(
            repaid=summary["total_repaid"],
            bal=summary["balance_amount"],
            od=summary["overdue_amount"],
        ),
        alert=True,
    )


@frappe.whitelist()
def refresh_repayment_summary(loan_name: str):
    """
    Public API: recompute and persist repayment summary on SHG Loan
    using only the child schedule table (Model A).
    """
    if not loan_name:
        frappe.throw(_("loan_name is required"))

    loan = frappe.get_doc(LOAN_DT, loan_name)

    summary = _compute_from_schedule(loan)
    _apply_to_loan(loan, summary)

    # Return the computed values so a Client Script can update the UI live
    return {
        "ok": True,
        "loan": loan.name,
        **summary,
    }