import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from shg.shg.utils.schedule_math import generate_reducing_balance_schedule, generate_flat_rate_schedule
from shg.shg.utils.account_helpers import get_or_create_member_receivable

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
    
    # Allow updates on submitted loans
    loan.flags.ignore_validate_update_after_submit = True
    loan.save(ignore_permissions=True)
    
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
    schedule = loan.repayment_schedule or []
    
    totals = {
        "principal": 0.0,
        "interest": 0.0,
        "total_payable": 0.0,
        "amount_paid": 0.0,
        "unpaid_balance": 0.0,
    }
    
    for row in schedule:
        totals["principal"] += float(row.get("principal_amount") or row.get("principal_component") or 0)
        totals["interest"] += float(row.get("interest_amount") or row.get("interest_component") or 0)
        totals["total_payable"] += float(row.get("total_payment") or 0)
        totals["amount_paid"] += float(row.get("amount_paid") or 0)
        totals["unpaid_balance"] += float(row.get("unpaid_balance") or 0)
    
    # Update loan fields
    loan.total_payable = totals["total_payable"]
    loan.total_repaid = totals["amount_paid"]
    loan.balance_amount = totals["unpaid_balance"]
    loan.overdue_amount = 0  # Will be calculated below
    
    # Calculate overdue amount
    today_date = getdate(nowdate())
    for row in schedule:
        due_date = getdate(row.due_date) if row.due_date else today_date
        if due_date < today_date and flt(row.unpaid_balance) > 0:
            loan.overdue_amount += flt(row.unpaid_balance)
    
    # Calculate next due date
    next_due_date = None
    for row in sorted(schedule, key=lambda x: getdate(x.due_date)):
        if flt(row.unpaid_balance) > 0:
            next_due_date = row.due_date
            break
    loan.next_due_date = next_due_date
    
    # Calculate last repayment date
    last_repayment_date = None
    for row in schedule:
        if row.status == "Paid" and row.actual_payment_date:
            payment_date = getdate(row.actual_payment_date)
            if not last_repayment_date or payment_date > last_repayment_date:
                last_repayment_date = payment_date
    loan.last_repayment_date = last_repayment_date
    
    # For monthly installment, take first row or division
    if loan.total_payable and loan.loan_period_months:
        loan.monthly_installment = loan.total_payable / loan.loan_period_months
    
    # Allow updates on submitted loans
    loan.flags.ignore_validate_update_after_submit = True
    loan.save(ignore_permissions=True)
    
    return totals

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
        if loan_name:
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
        "member_name": getattr(loan, "member_name", ""),
        "loan_amount": getattr(loan, "loan_amount", 0),
        "interest_rate": getattr(loan, "interest_rate", 0),
        "interest_type": getattr(loan, "interest_type", ""),
        "repayment_start_date": getattr(loan, "repayment_start_date", None),
        "monthly_installment": getattr(loan, "monthly_installment", 0),
        "total_payable": getattr(loan, "total_payable", 0),
        "total_repaid": getattr(loan, "total_repaid", 0),
        "balance_amount": getattr(loan, "balance_amount", 0),
        "overdue_amount": getattr(loan, "overdue_amount", 0),
        "next_due_date": getattr(loan, "next_due_date", None),
        "last_repayment_date": getattr(loan, "last_repayment_date", None)
    }
    
    return {
        "loan": summary,
        "schedule": schedule
    }