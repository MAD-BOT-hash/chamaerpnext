# file: shg/shg/patches/update_repayment_summary_hybrid.py
import frappe
from frappe.utils import flt, getdate, today

def _ensure_server_script(name: str, script_type: str, reference_doctype: str | None, script: str, event: str | None = None):
    existing = frappe.db.get_value("Server Script", {"name": name}, "name")
    data = {
        "doctype": "Server Script",
        "name": name,
        "script_type": script_type,
        "script": script,
        "disabled": 0,
    }
    if script_type == "DocType Event":
        data["reference_doctype"] = reference_doctype
        data["event"] = event

    if existing:
        doc = frappe.get_doc("Server Script", existing)
        doc.update(data)
        doc.save()
    else:
        frappe.get_doc(data).insert()
    frappe.db.commit()

# --- core compute (used by all hooks & API)
_COMPUTE_SCRIPT = r"""
import frappe
from frappe.utils import flt, getdate, today

def _hybrid_compute(doc):
    rows = doc.get("repayment_schedule") or []
    if not rows:
        # still clear fields so UI doesn't mislead
        doc.db_set({"monthly_installment": 0, "total_payable": 0, "total_repaid": 0,
                    "overdue_amount": 0, "balance_amount": flt(doc.loan_amount or 0),
                    "next_due_date": None}, update_modified=False)
        return

    total_payment = sum(flt(getattr(r, "total_payment", 0)) for r in rows)
    total_paid    = sum(flt(getattr(r, "amount_paid", 0))  for r in rows)
    # overdue = unpaid_balance of rows past due date
    today_d = getdate(today())
    overdue = 0
    next_due = None
    for r in rows:
        unpaid = flt(getattr(r, "unpaid_balance", 0))
        due = getdate(r.due_date) if getattr(r, "due_date", None) else None
        if unpaid > 0:
            if due:
                if due < today_d:
                    overdue += unpaid
                else:
                    # candidate for next due
                    next_due = due if (next_due is None or due < next_due) else next_due

    monthly = flt(getattr(rows[0], "total_payment", 0))
    balance = flt(total_payment) - flt(total_paid)
    if balance < 0: balance = 0

    # write even if submitted
    doc.flags.ignore_validate_update_after_submit = True
    doc.db_set({
        "monthly_installment": monthly,
        "total_payable": total_payment,
        "total_repaid": total_paid,
        "overdue_amount": overdue,
        "balance_amount": balance,
        "next_due_date": next_due
    }, update_modified=False)

# used by DocType Event hooks
_hybrid_compute(doc)
"""

# --- 1) SHG Loan — run on After Save
def _install_after_save():
    _ensure_server_script(
        name="SHG Loan | After Save — Hybrid Repayment Summary",
        script_type="DocType Event",
        reference_doctype="SHG Loan",
        event="After Save",
        script=_COMPUTE_SCRIPT,
    )

# --- 2) SHG Loan — run on After Submit (to refresh submitted loans)
def _install_after_submit():
    _ensure_server_script(
        name="SHG Loan | After Submit — Hybrid Repayment Summary",
        script_type="DocType Event",
        reference_doctype="SHG Loan",
        event="After Submit",
        script=_COMPUTE_SCRIPT,
    )

# --- 3) Public API to refresh from button
_API_SCRIPT = r"""
import frappe

@frappe.whitelist()
def refresh_repayment_summary(loan_name: str):
    loan = frappe.get_doc("SHG Loan", loan_name)
    # reuse the same logic as server scripts by importing it dynamically
    rows = loan.get("repayment_schedule") or []
    if not rows:
        loan.flags.ignore_validate_update_after_submit = True
        loan.db_set({"monthly_installment": 0, "total_payable": 0, "total_repaid": 0,
                     "overdue_amount": 0, "balance_amount": frappe.utils.flt(loan.loan_amount or 0),
                     "next_due_date": None}, update_modified=False)
        return {"ok": True}

    from frappe.utils import flt, getdate, today
    total_payment = sum(flt(getattr(r, "total_payment", 0)) for r in rows)
    total_paid    = sum(flt(getattr(r, "amount_paid", 0))  for r in rows)
    today_d = getdate(today())
    overdue = 0
    next_due = None
    for r in rows:
        unpaid = flt(getattr(r, "unpaid_balance", 0))
        due = getdate(r.due_date) if getattr(r, "due_date", None) else None
        if unpaid > 0:
            if due:
                if due < today_d:
                    overdue += unpaid
                else:
                    next_due = due if (next_due is None or due < next_due) else next_due

    monthly = flt(getattr(rows[0], "total_payment", 0))
    balance = flt(total_payment) - flt(total_paid)
    if balance < 0: balance = 0

    loan.flags.ignore_validate_update_after_submit = True
    loan.db_set({
        "monthly_installment": monthly,
        "total_payable": total_payment,
        "total_repaid": total_paid,
        "overdue_amount": overdue,
        "balance_amount": balance,
        "next_due_date": next_due
    }, update_modified=False)
    return {"ok": True}
"""

def _install_api():
    _ensure_server_script(
        name="SHG Loan | API — refresh_repayment_summary",
        script_type="API",
        reference_doctype=None,
        event=None,
        script=_API_SCRIPT,
    )

# --- 4) One-time backfill of existing loans
def _backfill_existing():
    from frappe.utils import flt, getdate, today  # ✅ FIX: import added here

    for d in frappe.get_all("SHG Loan", pluck="name"):
        loan = frappe.get_doc("SHG Loan", d)
        rows = loan.get("repayment_schedule") or []

        if not rows:
            loan.flags.ignore_validate_update_after_submit = True
            loan.db_set({
                "monthly_installment": 0,
                "total_payable": 0,
                "total_repaid": 0,
                "overdue_amount": 0,
                "balance_amount": flt(loan.loan_amount or 0),
                "next_due_date": None
            }, update_modified=False)
            continue

        total_payment = sum(flt(getattr(r, "total_payment", 0)) for r in rows)
        total_paid    = sum(flt(getattr(r, "amount_paid", 0))  for r in rows)
        today_d = getdate(today())
        overdue = 0
        next_due = None
        for r in rows:
            unpaid = flt(getattr(r, "unpaid_balance", 0))
            due = getdate(r.due_date) if getattr(r, "due_date", None) else None
            if unpaid > 0:
                if due:
                    if due < today_d:
                        overdue += unpaid
                    else:
                        next_due = due if (next_due is None or due < next_due) else next_due
        monthly = flt(getattr(rows[0], "total_payment", 0))
        balance = flt(total_payment) - flt(total_paid)
        if balance < 0: balance = 0
        loan.flags.ignore_validate_update_after_submit = True
        loan.db_set({
            "monthly_installment": monthly,
            "total_payable": total_payment,
            "total_repaid": total_paid,
            "overdue_amount": overdue,
            "balance_amount": balance,
            "next_due_date": next_due
        }, update_modified=False)

def execute():
    """Install hybrid summary updaters + API, and backfill."""
    _install_after_save()
    _install_after_submit()
    _install_api()
    _backfill_existing()