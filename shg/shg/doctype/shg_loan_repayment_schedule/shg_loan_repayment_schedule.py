import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowdate

class SHGLoanRepaymentSchedule(Document):
    """Child DocType; individual schedule rows."""

# ---------------------------------------------------------------------------
@frappe.whitelist()
def mark_installment_paid(loan_name, installment_no, amount=None, posting_date=None):
    """Mark a specific installment as paid."""
    loan = frappe.get_doc("SHG Loan", loan_name)
    schedule = None
    for row in loan.repayment_schedule:
        if row.installment_no == int(installment_no):
            schedule = row
            break
    if not schedule:
        frappe.throw(f"Installment {installment_no} not found in Loan {loan_name}")

    balance = flt(getattr(schedule, 'total_payment', 0)) - flt(getattr(schedule, 'amount_paid', 0))
    payment = flt(amount or balance)
    if payment <= 0:
        frappe.throw("No balance remaining for this installment.")

    schedule.amount_paid = flt(getattr(schedule, 'amount_paid', 0)) + payment
    schedule.unpaid_balance = flt(getattr(schedule, 'total_payment', 0)) - flt(getattr(schedule, 'amount_paid', 0))
    schedule.status = "Paid" if schedule.unpaid_balance <= 0.01 else "Partially Paid"
    schedule.payment_entry = f"AUTO-{nowdate()}"
    
    # Allow updates on submitted loans
    loan.flags.ignore_validate_update_after_submit = True
    loan.save(ignore_permissions=True)
    loan.reload()

    frappe.msgprint(
        f"Installment {installment_no} of Loan {loan_name} marked as Paid (KES {payment:,.2f})."
    )
    return {
        "installment_no": installment_no,
        "amount_paid": getattr(schedule, 'amount_paid', 0),
        "balance": getattr(schedule, 'unpaid_balance', 0),
        "status": getattr(schedule, 'status', ''),
    }


# ---------------------------------------------------------------------------
@frappe.whitelist()
def reverse_installment_payment(loan_name, installment_no):
    """Undo payment for a specific installment."""
    loan = frappe.get_doc("SHG Loan", loan_name)
    schedule = None
    for row in loan.repayment_schedule:
        if row.installment_no == int(installment_no):
            schedule = row
            break
    if not schedule:
        frappe.throw(f"Installment {installment_no} not found in Loan {loan_name}")

    schedule.amount_paid = 0
    schedule.unpaid_balance = flt(getattr(schedule, 'total_payment', 0))
    schedule.status = "Pending"
    schedule.payment_entry = None
    
    # Allow updates on submitted loans
    loan.flags.ignore_validate_update_after_submit = True
    loan.save(ignore_permissions=True)
    
    frappe.msgprint(
        f"Payment for Installment {installment_no} of Loan {loan_name} has been reversed."
    )
    return {"installment_no": installment_no, "status": "Pending", "balance": getattr(schedule, 'unpaid_balance', 0)}