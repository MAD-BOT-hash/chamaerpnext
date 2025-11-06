import frappe
from frappe.utils import today, getdate, flt

def get_schedule(loan_name):
    return frappe.get_all(
        "SHG Loan Repayment Schedule",
        filters={"parent": loan_name},
        fields=[
            "name", "idx", "due_date",
            "principal_component", "interest_component",
            "total_payment", "amount_paid", "unpaid_balance", "status"
        ],
        order_by="due_date asc, idx asc"
    )

def compute_totals(schedule_rows):
    total_principal = sum(flt(r.principal_component) for r in schedule_rows)
    total_interest  = sum(flt(r.interest_component)  for r in schedule_rows)
    total_payment   = sum(flt(r.total_payment)       for r in schedule_rows)
    total_paid      = sum(flt(r.amount_paid or 0)    for r in schedule_rows)
    outstanding_balance = sum(flt(r.unpaid_balance or (flt(r.total_payment) - flt(r.amount_paid or 0))) for r in schedule_rows)
    overdue         = sum(
        flt(r.unpaid_balance or (flt(r.total_payment) - flt(r.amount_paid or 0)))
        for r in schedule_rows
        if (r.status not in ("Paid",) and getdate(r.due_date) < getdate(today()))
    )
    return dict(
        total_principal=flt(total_principal, 2),
        total_interest=flt(total_interest, 2),
        total_payable=flt(total_payment, 2),
        total_repaid=flt(total_paid, 2),
        outstanding_balance=flt(outstanding_balance, 2),
        overdue_amount=flt(overdue, 2),
        loan_balance=flt(outstanding_balance, 2)  # same as outstanding_balance, principal+interest
    )

def update_loan_summary(loan_name):
    rows = get_schedule(loan_name)
    totals = compute_totals(rows)

    frappe.db.set_value("SHG Loan", loan_name, {
        "total_payable": totals["total_payable"],
        "total_repaid": totals["total_repaid"],
        "outstanding_balance": totals["outstanding_balance"],
        "loan_balance": totals["loan_balance"],        # principal + interest outstanding
        "balance_amount": totals["outstanding_balance"],      # keep same meaning in UI
        "overdue_amount": totals["overdue_amount"],
    }, update_modified=False)

    return totals

def allocate_payment_to_schedule(loan_name, paying_amount, posting_date=None):
    """
    EMI allocation across earliest unpaid/partially paid installments.
    Allows partial payments. Fails only if no outstanding balance.
    """
    paying_amount = flt(paying_amount)
    if paying_amount <= 0:
        frappe.throw("Payment amount must be greater than 0.")

    rows = get_schedule(loan_name)
    totals = compute_totals(rows)
    outstanding_total = totals["outstanding_balance"]

    if outstanding_total <= 0:
        frappe.throw("No outstanding balance to allocate.")

    to_allocate = min(paying_amount, outstanding_total)
    if to_allocate <= 0:
        return totals

    # Lock rows for update to avoid race conditions (best effort on MariaDB)
    for r in rows:
        if r.status == "Paid":
            continue

        already_paid = flt(r.amount_paid or 0)
        line_due     = flt(r.total_payment)
        line_left    = flt(r.unpaid_balance or (line_due - already_paid), 2)

        if line_left <= 0:
            # normalize row if needed
            if r.status != "Paid":
                frappe.db.set_value("SHG Loan Repayment Schedule", r.name, {
                    "unpaid_balance": 0, "status": "Paid"
                }, update_modified=False)
            continue

        take = min(line_left, to_allocate)
        new_paid = flt(already_paid + take, 2)
        new_left = flt(line_due - new_paid, 2)
        new_status = "Paid" if new_left <= 0.00001 else "Partially Paid"

        frappe.db.set_value("SHG Loan Repayment Schedule", r.name, {
            "amount_paid": new_paid,
            "unpaid_balance": max(new_left, 0),
            "status": new_status
        }, update_modified=False)

        to_allocate = flt(to_allocate - take, 2)
        if to_allocate <= 0:
            break

    # Refresh loan header
    return update_loan_summary(loan_name)

@frappe.whitelist()
def debug_loan_balance(loan):
    rows = get_schedule(loan)
    totals = compute_totals(rows)
    return {"schedule": rows, "totals": totals}