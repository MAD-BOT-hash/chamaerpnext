import frappe
from frappe.utils import flt, getdate, nowdate

def execute():
    """
    Recompute header totals for all existing loans.
    - Sum child paid_amount
    - Recompute totals
    - Set status to Closed if loan_balance == 0 and all items Paid
    - Rebuild overdue flags by due date
    """
    
    # Get all SHG Loans
    loans = frappe.get_all("SHG Loan", fields=["name"])
    
    for loan in loans:
        try:
            loan_name = loan.name
            loan_doc = frappe.get_doc("SHG Loan", loan_name)
            
            # Get all repayment schedule rows
            schedule_rows = frappe.get_all(
                "SHG Loan Repayment Schedule",
                filters={"parent": loan_name, "parenttype": "SHG Loan"},
                fields=["total_payment", "amount_paid", "unpaid_balance", "status", "due_date"]
            )
            
            # Calculate totals
            total_payable = sum(flt(row.get("total_payment", 0)) for row in schedule_rows)
            total_repaid = sum(flt(row.get("amount_paid", 0)) for row in schedule_rows)
            loan_balance = total_payable - total_repaid
            
            # Calculate overdue amount
            overdue_amount = 0
            today = getdate()
            all_paid = True
            
            for row in schedule_rows:
                total_payment = flt(row.get("total_payment", 0))
                amount_paid = flt(row.get("amount_paid", 0))
                remaining = total_payment - amount_paid
                
                # Check if overdue
                if row.get("due_date") and getdate(row.get("due_date")) < today and remaining > 0 and row.get("status") != "Paid":
                    overdue_amount += remaining
                    
                # Check if all rows are paid
                if remaining > 0:
                    all_paid = False
            
            # Update loan document
            loan_doc.total_payable = flt(total_payable, 2)
            loan_doc.total_repaid = flt(total_repaid, 2)
            loan_doc.loan_balance = flt(loan_balance, 2)
            loan_doc.balance_amount = flt(loan_balance, 2)  # Keep both fields consistent
            loan_doc.overdue_amount = flt(overdue_amount, 2)
            
            # Set status to Closed if loan is fully paid
            if all_paid and loan_balance <= 0:
                loan_doc.status = "Closed"
            
            # Save the document
            loan_doc.flags.ignore_validate_update_after_submit = True
            loan_doc.save(ignore_permissions=True)
            
            frappe.msgprint(f"Updated loan {loan_name}")
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to update loan {loan.get('name')}")
            continue
    
    frappe.db.commit()