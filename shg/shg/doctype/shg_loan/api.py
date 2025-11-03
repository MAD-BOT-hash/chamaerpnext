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
        return

    # Ensure doc is fresh
    loan.reload()

    # If summary method exists in class, use it
    # Use a safer approach instead of hasattr for Server Script compatibility
    try:
        # Try to get the method - if it doesn't exist, this will raise an AttributeError
        method = loan.update_repayment_summary
        method_exists = True
    except AttributeError:
        method_exists = False
    
    if method_exists:
        loan.update_repayment_summary()
        # Allow updates on submitted loans
        loan.flags.ignore_validate_update_after_submit = True
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

        # Use a safer approach instead of hasattr for Server Script compatibility
        try:
            status = getattr(row, 'status', None)
            has_status = status is not None
        except AttributeError:
            has_status = False
            status = None
        
        if has_status and status and status.lower() == "overdue":
            # Use a safer approach instead of hasattr for Server Script compatibility
            try:
                unpaid_balance = getattr(row, 'unpaid_balance', 0)
                has_unpaid_balance = unpaid_balance is not None
            except AttributeError:
                has_unpaid_balance = False
                unpaid_balance = 0
            
            if has_unpaid_balance:
                overdue_amount += flt(unpaid_balance)

    loan.total_principal = total_principal
    loan.total_interest = total_interest
    loan.total_paid = total_paid
    loan.overdue_amount = overdue_amount
    loan.balance_amount = (total_principal + total_interest) - total_paid

    # Allow updates on submitted loans
    loan.flags.ignore_validate_update_after_submit = True
    loan.save(ignore_permissions=True)
    frappe.db.commit()
    
    return {"status": "success"}