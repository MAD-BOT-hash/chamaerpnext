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