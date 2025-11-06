import frappe

def execute():
    """Update loan summary calculation to correctly reflect outstanding balance."""
    
    # Reload the SHG Loan doctype to ensure the new fields are available
    frappe.reload_doc("shg", "doctype", "shg_loan")
    frappe.reload_doc("shg", "doctype", "shg_loan_repayment_schedule")
    
    # Update existing loan records to ensure they have the correct summary calculations
    loans = frappe.get_all("SHG Loan", filters={"docstatus": 1})
    for loan in loans:
        try:
            loan_doc = frappe.get_doc("SHG Loan", loan.name)
            
            # Calculate totals from repayment schedule
            schedule = frappe.get_all(
                "SHG Loan Repayment Schedule",
                filters={"parent": loan.name},
                fields=["principal_component", "interest_component", "amount_paid", "unpaid_balance", "due_date", "status"]
            )
            
            # Calculate totals
            total_principal_payable = sum(flt(r.get("principal_component", 0)) for r in schedule)
            total_interest_payable = sum(flt(r.get("interest_component", 0)) for r in schedule)
            total_payable_amount = flt(total_principal_payable) + flt(total_interest_payable)
            total_amount_paid = sum(flt(r.get("amount_paid", 0)) for r in schedule)
            outstanding_amount = flt(total_payable_amount) - flt(total_amount_paid)
            
            # Calculate overdue amount
            overdue_amount = 0
            from frappe.utils import getdate, nowdate
            today_date = getdate(nowdate())
            for r in schedule:
                due_date = getdate(r.get("due_date")) if r.get("due_date") else today_date
                # Overdue if not paid and due date is in the past
                if r.get("status") != "Paid" and due_date < today_date and flt(r.get("unpaid_balance", 0)) > 0:
                    overdue_amount += flt(r.get("unpaid_balance", 0))
            
            # Update loan fields
            loan_doc.total_principal_payable = total_principal_payable
            loan_doc.total_interest_payable = total_interest_payable
            loan_doc.total_payable_amount = total_payable_amount
            loan_doc.total_amount_paid = total_amount_paid
            loan_doc.outstanding_amount = outstanding_amount
            loan_doc.overdue_amount = overdue_amount
            
            # Update loan status based on calculations
            if outstanding_amount <= 0:
                loan_doc.loan_status = "Completed"
            elif overdue_amount > 0:
                loan_doc.loan_status = "Overdue"
            else:
                loan_doc.loan_status = "Active"
            
            # Save the document
            loan_doc.flags.ignore_validate_update_after_submit = True
            loan_doc.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to update loan summary for {loan.name}")
            pass  # Skip errors to avoid breaking the patch
            
    frappe.db.commit()

def flt(val, precision=None):
    """Helper function to convert value to float."""
    try:
        if precision is not None:
            return round(float(val or 0), precision)
        return float(val or 0)
    except:
        return 0.0