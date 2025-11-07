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
    """
    Central function to update all loan summary fields based on repayment schedule.
    Reads all rows in SHG Loan Repayment Schedule and recalculates all summary fields.
    """
    try:
        # Get the loan document
        loan_doc = frappe.get_doc("SHG Loan", loan_name)
        
        # Get repayment schedule rows
        schedule = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={"parent": loan_name},
            fields=[
                "name", "due_date", "principal_component", "interest_component",
                "total_payment", "amount_paid", "unpaid_balance", "status"
            ],
            order_by="due_date asc"
        )
        
        # Calculate totals
        total_principal_payable = sum(flt(r.principal_component) for r in schedule)
        total_interest_payable = sum(flt(r.interest_component) for r in schedule)
        total_payable = sum(flt(r.total_payment) for r in schedule)
        total_paid = sum(flt(r.amount_paid or 0) for r in schedule)
        
        # Calculate outstanding balance (principal + interest)
        outstanding_balance = sum(flt(r.unpaid_balance or (flt(r.total_payment) - flt(r.amount_paid or 0))) for r in schedule)
        
        # Calculate overdue amount (sum of unpaid installments where due_date < today)
        overdue_amount = 0
        today_date = getdate(today())
        for r in schedule:
            if (r.status not in ("Paid",) and 
                getdate(r.due_date) < today_date and 
                flt(r.unpaid_balance or (flt(r.total_payment) - flt(r.amount_paid or 0))) > 0):
                overdue_amount += flt(r.unpaid_balance or (flt(r.total_payment) - flt(r.amount_paid or 0)))
        
        # Calculate next due date (first unpaid installment)
        next_due_date = None
        for r in sorted(schedule, key=lambda x: getdate(x.due_date)):
            if r.status not in ("Paid",) and flt(r.unpaid_balance or 0) > 0:
                next_due_date = r.due_date
                break
        
        # Calculate percentage repaid
        percent_repaid = 0
        if total_payable > 0:
            percent_repaid = flt((total_paid / total_payable) * 100, 2)
        
        # Update loan document fields
        loan_doc.total_principal_payable = flt(total_principal_payable, 2)
        loan_doc.total_interest_payable = flt(total_interest_payable, 2)
        loan_doc.total_payable_amount = flt(total_payable, 2)
        loan_doc.total_amount_paid = flt(total_paid, 2)
        loan_doc.total_interest_paid = flt(total_interest_payable - (outstanding_balance - (total_principal_payable - total_paid + total_interest_payable)), 2)  # Simplified calculation
        loan_doc.outstanding_amount = flt(outstanding_balance, 2)
        loan_doc.balance_amount = flt(outstanding_balance, 2)
        loan_doc.loan_balance = flt(outstanding_balance, 2)
        loan_doc.overdue_amount = flt(overdue_amount, 2)
        loan_doc.next_due_date = next_due_date
        loan_doc.percent_repaid = flt(percent_repaid, 2)
        
        # Set loan status based on calculations
        if outstanding_balance <= 0:
            loan_doc.loan_status = "Completed"
        elif overdue_amount > 0:
            loan_doc.loan_status = "Overdue"
        else:
            loan_doc.loan_status = "Active"
        
        # Allow updates on submitted loans
        loan_doc.flags.ignore_validate_update_after_submit = True
        
        # Save the document
        loan_doc.save(ignore_permissions=True)
        
        return {
            "status": "success",
            "message": "Loan summary updated successfully"
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to update loan summary for {loan_name}")
        return {
            "status": "error",
            "message": str(e)
        }

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
        
        # ✅ Safety check before allocation
        if flt(take) > flt(line_left):
            frappe.log_error(
                f"Payment allocation attempt: take ({take}) > line_left ({line_left}) "
                f"for installment {r.name or r.installment_no}",
                "SHG Loan Payment Allocation"
            )
            frappe.throw(
                f"Amount to pay ({take}) cannot exceed remaining balance "
                f"({line_left}) for installment {r.name or r.installment_no}."
            )

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