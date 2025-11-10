import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowdate

class SHGLoanRepaymentSchedule(Document):
    """Child DocType; individual schedule rows."""

# ---------------------------------------------------------------------------
@frappe.whitelist()
def mark_installment_paid(loan_name, installment_no, amount=None, posting_date=None):
    """Mark a specific installment as paid by creating a loan repayment document."""
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

    # Create a loan repayment document
    repayment_doc = frappe.new_doc("SHG Loan Repayment")
    repayment_doc.loan = loan_name
    repayment_doc.member = loan.member
    repayment_doc.total_paid = payment
    repayment_doc.posting_date = posting_date or nowdate()
    repayment_doc.repayment_date = posting_date or nowdate()
    repayment_doc.reference_schedule_row = schedule.name  # Link to specific schedule row
    
    # Save and submit the repayment
    repayment_doc.insert(ignore_permissions=True)
    repayment_doc.submit()
    
    # Reload the loan to get updated values
    loan.reload()

    frappe.msgprint(
        f"Installment {installment_no} of Loan {loan_name} marked as Paid (KES {payment:,.2f}). "
        f"Payment Entry {repayment_doc.payment_entry} created."
    )
    return {
        "installment_no": installment_no,
        "amount_paid": getattr(schedule, 'amount_paid', 0),
        "balance": getattr(schedule, 'unpaid_balance', 0),
        "status": getattr(schedule, 'status', ''),
        "payment_entry": repayment_doc.payment_entry
    }


# ---------------------------------------------------------------------------
@frappe.whitelist()
def reverse_installment_payment(loan_name, installment_no):
    """Reverse payment for a specific installment."""
    loan = frappe.get_doc("SHG Loan", loan_name)
    schedule = None
    for row in loan.repayment_schedule:
        if row.installment_no == int(installment_no):
            schedule = row
            break
    if not schedule:
        frappe.throw(f"Installment {installment_no} not found in Loan {loan_name}")

    # Find the repayment document linked to this schedule row
    repayment_name = schedule.payment_entry
    if not repayment_name:
        frappe.throw(f"No payment found for Installment {installment_no}")

    # Cancel the repayment document
    try:
        repayment_doc = frappe.get_doc("SHG Loan Repayment", repayment_name)
        repayment_doc.cancel()
        
        # Reload the loan to get updated values
        loan.reload()
        
        frappe.msgprint(
            f"Payment for Installment {installment_no} of Loan {loan_name} has been reversed."
        )
        return {"installment_no": installment_no, "status": "Pending", "balance": getattr(schedule, 'unpaid_balance', 0)}
    except Exception as e:
        frappe.throw(f"Failed to reverse payment: {str(e)}")