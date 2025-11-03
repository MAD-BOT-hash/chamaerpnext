import frappe
from frappe.utils import getdate, today

def flag_overdue_loans():
    """Daily scheduler task to flag overdue loan installments."""
    frappe.msgprint("Flagging overdue loan installments...")
    
    # Get today's date
    today_date = getdate(today())
    
    # Find all pending installments that are overdue
    overdue_installments = frappe.db.sql("""
        SELECT name, parent
        FROM `tabSHG Loan Repayment Schedule`
        WHERE status = 'Pending' 
        AND due_date < %s
        AND unpaid_balance > 0
    """, (today_date,), as_dict=1)
    
    updated_count = 0
    
    # Update each overdue installment
    for installment in overdue_installments:
        try:
            doc = frappe.get_doc("SHG Loan Repayment Schedule", installment.name)
            doc.status = "Overdue"
            doc.save(ignore_permissions=True)
            updated_count += 1
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to flag installment {installment.name} as overdue")
    
    # Update loan summaries for loans with overdue installments
    if overdue_installments:
        loan_names = list(set([inst.parent for inst in overdue_installments]))
        for loan_name in loan_names:
            try:
                from shg.shg.api.loan import refresh_repayment_summary
                refresh_repayment_summary(loan_name)
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"Failed to refresh summary for loan {loan_name}")
    
    frappe.msgprint(f"Flagged {updated_count} installments as overdue")