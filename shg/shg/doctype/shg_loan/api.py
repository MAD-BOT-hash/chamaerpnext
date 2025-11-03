import frappe
from frappe.utils import flt, getdate, today

@frappe.whitelist()
def refresh_repayment_summary(loan_name: str):
    """Refresh repayment summary and detail values for SHG Loan specified by loan_name."""
    # Validate input
    if not loan_name:
        frappe.throw("Loan name is required", title="Invalid Input")
        
    try:
        loan = frappe.get_doc("SHG Loan", loan_name)
    except frappe.DoesNotExistError:
        frappe.throw(f"Loan '{loan_name}' not found", title="Loan Not Found")

    # Ensure doc is fresh
    loan.reload()

    # If summary method exists in class, use it
    if hasattr(loan, "update_repayment_summary"):
        loan.update_repayment_summary()
        loan.save(ignore_permissions=True)
        frappe.db.commit()
        return {"status": "success"}

    # Fallback: update summary manually from child repayment table
    total_principal = 0
    total_interest = 0
    total_paid = 0
    overdue_amount = 0

    for row in loan.get("repayment_schedule", []):
        total_principal += flt(row.principal_component)
        total_interest += flt(row.interest_component)
        total_paid += flt(row.amount_paid)

        if row.status and row.status.lower() == "overdue":
            overdue_amount += flt(row.unpaid_balance)

    loan.total_principal = total_principal
    loan.total_interest = total_interest
    loan.total_paid = total_paid
    loan.overdue_amount = overdue_amount
    loan.balance_amount = (total_principal + total_interest) - total_paid

    loan.save(ignore_permissions=True)
    frappe.db.commit()
    
    return {"status": "success"}