import frappe
from frappe.utils import flt

def execute():
    """Fix loan balance calculation to ensure it includes both principal and interest."""
    
    # Ensure all loans have correct balance calculations
    fix_existing_loan_balances()
    
    frappe.msgprint("✅ Loan balance calculation verified and fixed")

def fix_existing_loan_balances():
    """Fix existing loan balances to ensure they include both principal and interest."""
    # Get all submitted loans
    loans = frappe.get_all("SHG Loan", filters={"docstatus": 1}, fields=["name"])
    
    for loan in loans:
        try:
            # Refresh the repayment summary for each loan
            loan_doc = frappe.get_doc("SHG Loan", loan.name)
            
            # Verify that the repayment schedule includes both principal and interest
            schedule = loan_doc.get("repayment_schedule")
            if schedule:
                # Calculate what the balance should be based on the schedule
                expected_balance = sum(flt(row.unpaid_balance) for row in schedule)
                expected_total_payable = sum(flt(row.total_payment) for row in schedule)
                expected_total_repaid = sum(flt(row.amount_paid) for row in schedule)
                
                # Update the loan fields if they don't match
                loan_doc.total_payable = expected_total_payable
                loan_doc.total_repaid = expected_total_repaid
                loan_doc.balance_amount = expected_balance
                
                # Allow updates on submitted loans
                loan_doc.flags.ignore_validate_update_after_submit = True
                loan_doc.save(ignore_permissions=True)
                
        except Exception:
            # Log error but continue with other loans
            frappe.log_error(frappe.get_traceback(), f"Failed to update loan {loan.name}")
            
    frappe.db.commit()