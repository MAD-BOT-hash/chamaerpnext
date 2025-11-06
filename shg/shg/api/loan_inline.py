import frappe
from frappe import _

def _schedule_fieldname():
    """Find the schedule child table field on SHG Loan (defaults to 'repayment_schedule')."""
    meta = frappe.get_meta("SHG Loan")
    for df in meta.fields:
        if df.fieldtype == "Table" and df.options == "SHG Loan Repayment Schedule":
            return df.fieldname
    return "repayment_schedule"

def _row_remaining(row):
    total = (row.total_payment or 0)  # expected EMI for the row
    paid  = (row.paid_amount or 0)
    return max(total - paid, 0)

@frappe.whitelist()
def pull_unpaid_installments(loan):
    """Fill the loan's schedule grid with only unpaid (or partly-paid) rows on the form, and compute 'remaining_amount'."""
    doc = frappe.get_doc("SHG Loan", loan)
    grid = _schedule_fieldname()
    updated = []
    for row in doc.get(grid) or []:
        rem = _row_remaining(row)
        row.remaining_amount = rem
        # clear any previous selection for a fresh pull
        row.pay_now = 0
        row.amount_to_pay = None
        if rem > 0:
            updated.append(dict(name=row.name, remaining_amount=rem))
    doc.save(ignore_permissions=True)
    return {"count": len(updated)}

@frappe.whitelist()
def compute_inline_totals(loan):
    """Return live totals for Selected To Pay, Overdue, and Outstanding (P+I)."""
    doc = frappe.get_doc("SHG Loan", loan)
    grid = _schedule_fieldname()

    selected_to_pay = 0
    overdue = 0
    outstanding = 0

    today = frappe.utils.today()

    for row in doc.get(grid) or []:
        rem = _row_remaining(row)
        outstanding += rem
        if row.due_date and row.due_date < today and rem > 0:
            overdue += rem
        if int(row.pay_now or 0) == 1 and (row.amount_to_pay or 0) > 0:
            selected_to_pay += min(float(row.amount_to_pay), float(rem))

    return {
        "selected": selected_to_pay,
        "overdue": overdue,
        "outstanding": outstanding
    }

@frappe.whitelist()
def post_inline_repayments(loan):
    """
    Apply selected partial payments against schedule rows.
    - Validates not exceeding per-row remaining.
    - Updates paid_amount & status.
    - Auto-closes rows when fully paid.
    - Recomputes loan-level aggregates (Total Repaid / Balance / Overdue).
    NOTE: Hook your GL/Payment Entry creation here if needed.
    """
    doc = frappe.get_doc("SHG Loan", loan)
    grid = _schedule_fieldname()

    changes = []
    for row in doc.get(grid) or []:
        if not int(row.pay_now or 0):
            continue
        amt = float(row.amount_to_pay or 0)
        if amt <= 0:
            continue

        remaining = _row_remaining(row)
        if amt > remaining + 1e-9:
            frappe.throw(_("Repayment ({0}) exceeds remaining balance ({1}) for installment #{2}").format(
                frappe.utils.fmt_money(amt), frappe.utils.fmt_money(remaining), (row.idx or "")
            ))

        row.paid_amount = float(row.paid_amount or 0) + amt
        new_remaining = _row_remaining(row)
        row.status = "Paid" if new_remaining <= 1e-9 else "Partly Paid"
        row.remaining_amount = new_remaining

        # reset inline inputs after posting
        row.pay_now = 0
        row.amount_to_pay = None

        changes.append(dict(rowname=row.name, posted=amt, status=row.status, remaining=new_remaining))

    # Recompute loan level totals (Outstanding P+I, Total Repaid, Balance)
    _recompute_loan_totals(doc, grid)

    doc.save(ignore_permissions=True)
    return {"posted_rows": len(changes), "rows": changes}

def _recompute_loan_totals(doc, grid):
    total_due_all = 0.0
    total_paid_all = 0.0
    overdue = 0.0
    today = frappe.utils.today()

    for r in doc.get(grid) or []:
        total_due_all += float(r.total_payment or 0)
        total_paid_all += float(r.paid_amount or 0)
        if r.due_date and r.due_date < today:
            remaining = _row_remaining(r)
            overdue += max(remaining, 0)

    outstanding = max(total_due_all - total_paid_all, 0.0)

    # Map to your existing parent fields; adjust if your fieldnames differ
    doc.db_set("total_repaid", total_paid_all, commit=False)
    doc.db_set("loan_balance", outstanding, commit=False)     # a.k.a. full outstanding (P + I)
    doc.db_set("balance_amount", outstanding, commit=False)   # keep both aligned if both exist
    doc.db_set("overdue_amount", overdue, commit=False)
