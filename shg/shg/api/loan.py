import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from shg.shg.utils.schedule_math import generate_reducing_balance_schedule, generate_flat_rate_schedule
from shg.shg.utils.account_helpers import get_or_create_member_receivable
from shg.shg.loan_utils import allocate_payment_to_schedule, update_loan_summary, get_schedule

@frappe.whitelist()
def get_unpaid_installments(loan):
    rows = get_schedule(loan)
    return [r for r in rows if (r.get("status") not in ("Paid",) and flt(r.get("remaining_amount") or (flt(r["total_payment"]) - flt(r.get("amount_paid") or 0))) > 0)]

@frappe.whitelist()
def post_repayment_allocation(loan, amount):
    amount = flt(amount)
    totals = allocate_payment_to_schedule(loan, amount)
    return {"message": "Repayment allocated", "totals": totals}

@frappe.whitelist()
def debug_loan_balance(loan_name):
    """
    Debug endpoint to return detailed loan balance information.
    
    Args:
        loan_name (str): Name of the SHG Loan document
        
    Returns:
        dict: Detailed loan balance information
    """
    try:
        # Get loan document
        loan_doc = frappe.get_doc("SHG Loan", loan_name)
        
        # Get repayment schedule
        schedule = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={"parent": loan_name},
            fields=["*"],
            order_by="due_date"
        )
        
        # Get repayments
        repayments = frappe.get_all(
            "SHG Loan Repayment",
            filters={"loan": loan_name, "docstatus": 1},
            fields=["*"],
            order_by="posting_date"
        )
        
        # Calculate outstanding balance using the new function
        from shg.shg.doctype.shg_loan.shg_loan import get_outstanding_balance
        outstanding_info = get_outstanding_balance(loan_name)
        
        return {
            "loan": {
                "name": loan_doc.name,
                "member": loan_doc.member,
                "loan_amount": loan_doc.loan_amount,
                "total_payable": loan_doc.total_payable,
                "total_repaid": loan_doc.total_repaid,
                "balance_amount": loan_doc.balance_amount,
                "loan_balance": loan_doc.loan_balance,
                "overdue_amount": loan_doc.overdue_amount
            },
            "schedule": schedule,
            "repayments": repayments,
            "outstanding": outstanding_info
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to debug loan balance for {loan_name}")
        frappe.throw(f"Failed to debug loan balance: {str(e)}")

@frappe.whitelist()
def generate_schedule(loan_name):
    """
    Generate repayment schedule for a loan.
    
    Args:
        loan_name (str): Name of the loan document
        
    Returns:
        dict: Status and message
    """
    if not loan_name:
        frappe.throw(_("Loan name is required"))
        
    loan = frappe.get_doc("SHG Loan", loan_name)
    
    # Clear existing schedule
    loan.repayment_schedule = []
    
    principal = flt(loan.loan_amount)
    months = int(loan.loan_period_months)
    start_date = loan.repayment_start_date or frappe.utils.add_months(loan.disbursement_date or frappe.utils.today(), 1)
    interest_type = getattr(loan, "interest_type", "Reducing Balance")
    
    if interest_type == "Flat Rate":
        schedule = generate_flat_rate_schedule(principal, loan.interest_rate, months, start_date)
    else:
        schedule = generate_reducing_balance_schedule(principal, loan.interest_rate, months, start_date)
    
    # Add schedule rows to loan
    for row_data in schedule:
        loan.append("repayment_schedule", row_data)
    
    loan.save()
    
    return {
        "status": "success",
        "message": _("Repayment schedule generated successfully with {0} installments").format(len(schedule))
    }

@frappe.whitelist()
def refresh_repayment_summary(loan_name):
    """
    Recalculate repayment summary from schedule and update loan fields.
    
    Args:
        loan_name (str): Name of the loan document
        
    Returns:
        dict: Computed summary values
    """
    if not loan_name:
        frappe.throw(_("Loan name is required"))
        
    loan = frappe.get_doc("SHG Loan", loan_name)
    
    # Compute repayment summary using the new method
    summary = loan.compute_repayment_summary()
    
    # Update loan fields
    loan.total_payable = summary["total_payable"]
    loan.total_repaid = summary["total_repaid"]
    loan.balance_amount = summary["balance_amount"]
    loan.overdue_amount = summary["overdue_amount"]
    loan.next_due_date = summary["next_due_date"]
    loan.last_repayment_date = summary["last_repayment_date"]
    loan.monthly_installment = summary["monthly_installment"]
    
    # Update loan balance
    from shg.shg.doctype.shg_loan.shg_loan import get_loan_balance
    loan.loan_balance = get_loan_balance(loan_name)
    
    # Allow updates on submitted loans
    loan.flags.ignore_validate_update_after_submit = True
    loan.save(ignore_permissions=True)
    
    return summary

@frappe.whitelist()
def get_member_loan_statement(member=None, loan_name=None, date_from=None, date_to=None):
    """
    Returns loan + repayment schedule for a given member or loan_id.
    
    Args:
        member (str, optional): Member ID
        loan_name (str, optional): Loan name
        date_from (str, optional): Start date filter (YYYY-MM-DD)
        date_to (str, optional): End date filter (YYYY-MM-DD)
        
    Returns:
        dict: Loan details and repayment schedule
    """
    if not (loan_name or member):
        frappe.throw(_("Either Member or Loan ID is required."))
    
    # Initialize loan variable
    loan = None
    
    # Try loading by loan_name first
    if loan_name:
        loan = frappe.get_doc("SHG Loan", loan_name)
    elif member:
        # fallback: get latest active loan for that member
        loan_name = frappe.db.get_value(
            "SHG Loan", 
            {"member": member, "docstatus": 1}, 
            "name"
        )
        if not loan_name:
            frappe.throw(_("No active loan found for this member."))
        loan = frappe.get_doc("SHG Loan", loan_name)
    
    # Ensure we have a loan
    if not loan:
        frappe.throw(_("Either Member or Loan ID is required."))
    
    # Build repayment details
    filters = {"parent": loan.name}
    
    # Apply date filters if provided
    if date_from:
        filters["due_date"] = [">=", date_from]
    if date_to:
        if "due_date" in filters:
            filters["due_date"][1] = "<=", date_to
        else:
            filters["due_date"] = ["<=", date_to]
    
    schedule = frappe.get_all(
        "SHG Loan Repayment Schedule",
        filters=filters,
        fields=[
            "installment_no",
            "due_date",
            "principal_component as principal_amount",
            "interest_component as interest_amount",
            "total_payment",
            "amount_paid",
            "unpaid_balance",
            "status",
            "actual_payment_date"
        ],
        order_by="installment_no asc"
    )
    
    summary = {
        "loan_id": loan.name,
        "member_name": loan.member_name,
        "loan_amount": loan.loan_amount,
        "interest_rate": loan.interest_rate,
        "interest_type": loan.interest_type,
        "repayment_start_date": loan.repayment_start_date,
        "monthly_installment": loan.monthly_installment,
        "total_payable": loan.total_payable,
        "total_repaid": loan.total_repaid,
        "balance_amount": loan.balance_amount,
        "overdue_amount": loan.overdue_amount,
        "next_due_date": loan.next_due_date,
        "last_repayment_date": loan.last_repayment_date
    }
    
    return {
        "loan_details": summary,
        "repayment_schedule": schedule,
        "count": len(schedule)
    }

@frappe.whitelist()
def mark_installment_paid(loan_name, schedule_row, amount):
    """
    Mark a specific installment as paid.
    
    Args:
        loan_name (str): Name of the loan document
        schedule_row (str): Name of the schedule row
        amount (float): Amount to mark as paid
        
    Returns:
        dict: Status and message
    """
    if not loan_name or not schedule_row:
        frappe.throw(_("Loan name and schedule row are required"))
        
    # Get the schedule row
    schedule_doc = frappe.get_doc("SHG Loan Repayment Schedule", schedule_row)
    
    if schedule_doc.parent != loan_name:
        frappe.throw(_("Schedule row does not belong to the specified loan"))
        
    # Mark as paid
    amount_to_pay = flt(amount or schedule_doc.total_payment)
    schedule_doc.amount_paid = amount_to_pay
    schedule_doc.unpaid_balance = max(0, flt(schedule_doc.total_payment) - amount_to_pay)
    schedule_doc.status = "Paid" if schedule_doc.unpaid_balance == 0 else "Partially Paid"
    schedule_doc.actual_payment_date = frappe.utils.today()
    schedule_doc.save()
    
    # Refresh loan summary
    refresh_repayment_summary(loan_name)
    
    return {
        "status": "success",
        "message": _("Installment marked as paid successfully")
    }