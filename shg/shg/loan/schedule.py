import frappe
from frappe.utils import flt, getdate, today

def get_schedule(loan_name):
    """Get repayment schedule for a loan."""
    return frappe.get_all(
        "SHG Loan Repayment Schedule",
        filters={"parent": loan_name},
        fields=[
            "name", "idx", "due_date",
            "principal_component", "interest_component",
            "total_payment", "amount_paid", "unpaid_balance", "status"
        ],
        order_by="due_date asc, idx asc"
    )

def compute_totals(schedule_rows):
    """Compute totals from schedule rows."""
    total_principal = sum(flt(r.get("principal_component", 0)) for r in schedule_rows)
    total_interest = sum(flt(r.get("interest_component", 0)) for r in schedule_rows)
    total_payment = sum(flt(r.get("total_payment", 0)) for r in schedule_rows)
    total_paid = sum(flt(r.get("amount_paid", 0) or 0) for r in schedule_rows)
    outstanding_balance = sum(flt(r.get("unpaid_balance", 0) or (
        flt(r.get("total_payment", 0)) - flt(r.get("amount_paid", 0) or 0)
    )) for r in schedule_rows)
    
    overdue = sum(
        flt(r.get("unpaid_balance", 0) or (
            flt(r.get("total_payment", 0)) - flt(r.get("amount_paid", 0) or 0)
        ))
        for r in schedule_rows
        if (r.get("status") not in ("Paid",) and getdate(r.get("due_date")) < getdate(today()))
    )
    
    return dict(
        total_principal=flt(total_principal, 2),
        total_interest=flt(total_interest, 2),
        total_payable=flt(total_payment, 2),
        total_repaid=flt(total_paid, 2),
        outstanding_balance=flt(outstanding_balance, 2),
        overdue_amount=flt(overdue, 2),
        loan_balance=flt(outstanding_balance, 2)  # same as outstanding_balance, principal+interest
    )

def build_schedule(loan_doc):
    """
    Generates amortization schedule per interest_type (Flat vs Reducing).
    
    Args:
        loan_doc: SHG Loan document
        
    Returns:
        list: Schedule rows
    """
    if not loan_doc.loan_amount or not loan_doc.interest_rate or not loan_doc.loan_period_months:
        return []
        
    schedule = []
    principal = flt(loan_doc.loan_amount)
    interest_rate = flt(loan_doc.interest_rate)
    months = loan_doc.loan_period_months
    frequency = loan_doc.repayment_frequency or "Monthly"
    
    # Calculate frequency multiplier
    freq_multiplier = 1
    if frequency == "Quarterly":
        freq_multiplier = 3
    elif frequency == "Half-Yearly":
        freq_multiplier = 6
    elif frequency == "Yearly":
        freq_multiplier = 12
    
    # Calculate EMI based on interest type
    if loan_doc.interest_type == "Flat Rate":
        # Flat rate: interest calculated on original principal
        total_interest = principal * (interest_rate / 100) * (months / 12)
        total_amount = principal + total_interest
        emi = total_amount / months
        
        # For flat rate, principal and interest components are fixed
        monthly_interest = total_interest / months
        monthly_principal = principal / months
        
        for i in range(1, months + 1):
            due_date = add_months(getdate(loan_doc.repayment_start_date), (i - 1) * freq_multiplier)
            schedule.append({
                "installment_no": i,
                "due_date": due_date,
                "emi_amount": flt(emi, 2),
                "principal_component": flt(monthly_principal, 2),
                "interest_component": flt(monthly_interest, 2),
                "paid_amount": 0,
                "status": "Pending"
            })
    else:
        # Reducing balance: interest calculated on reducing principal
        monthly_rate = (interest_rate / 100) / 12
        emi = principal * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
        
        remaining_principal = principal
        for i in range(1, months + 1):
            due_date = add_months(getdate(loan_doc.repayment_start_date), (i - 1) * freq_multiplier)
            interest_component = remaining_principal * monthly_rate
            principal_component = emi - interest_component
            remaining_principal -= principal_component
            
            schedule.append({
                "installment_no": i,
                "due_date": due_date,
                "emi_amount": flt(emi, 2),
                "principal_component": flt(principal_component, 2),
                "interest_component": flt(interest_component, 2),
                "paid_amount": 0,
                "status": "Pending"
            })
    
    return schedule

def add_months(date, months):
    """Add months to a date."""
    from dateutil.relativedelta import relativedelta
    return getdate(date) + relativedelta(months=months)