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

        # Check for overdue status and amount
        try:
            status = getattr(row, 'status', None)
            unpaid_balance = getattr(row, 'unpaid_balance', 0)
        except AttributeError:
            status = None
            unpaid_balance = 0
         
        # Only add to overdue if status is overdue AND unpaid_balance is > 0
        if status and status.lower() == "overdue" and flt(unpaid_balance) > 0:
            overdue_amount += flt(unpaid_balance)

    # Update loan fields using correct field names that exist in doctype
    try:
        loan.total_principal_payable = total_principal
        loan.total_interest_payable = total_interest
        loan.total_amount_paid = total_paid
        loan.overdue_amount = overdue_amount
        loan.outstanding_amount = (total_principal + total_interest) - total_paid
    except AttributeError as e:
        frappe.log_error(f"Field assignment error: {str(e)}", "Loan Summary Update Failed")
        # Don't fail the whole update if some fields don't exist
        try:
            loan.total_principal_payable = total_principal
        except:
            pass
        try:
            loan.total_interest_payable = total_interest
        except:
            pass
        try:
            loan.total_amount_paid = total_paid
        except:
            pass

    # Allow updates on submitted loans
    loan.flags.ignore_validate_update_after_submit = True
    loan.save(ignore_permissions=True)
    frappe.db.commit()
    
    return {"status": "success"}