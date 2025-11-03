import frappe
from frappe.utils import flt, add_months

def calculate_emi(principal, annual_interest_rate, months):
    """
    Calculate EMI (Equated Monthly Installment) for reducing balance loans.
    
    Args:
        principal (float): Loan principal amount
        annual_interest_rate (float): Annual interest rate as percentage (e.g., 12 for 12%)
        months (int): Loan period in months
        
    Returns:
        float: Monthly EMI amount
    """
    if months <= 0:
        return 0
    
    # Monthly interest rate
    monthly_rate = flt(annual_interest_rate) / 100.0 / 12.0
    
    # If interest rate is 0, simple division
    if monthly_rate == 0:
        return principal / months
    
    # EMI formula: P * r * (1 + r)^n / ((1 + r)^n - 1)
    emi = principal * monthly_rate * ((1 + monthly_rate) ** months) / (((1 + monthly_rate) ** months) - 1)
    return emi

def calculate_flat_interest(principal, annual_interest_rate, months):
    """
    Calculate total interest for flat rate loans.
    
    Args:
        principal (float): Loan principal amount
        annual_interest_rate (float): Annual interest rate as percentage (e.g., 12 for 12%)
        months (int): Loan period in months
        
    Returns:
        dict: Contains total_interest, monthly_interest, total_amount, monthly_installment
    """
    # Total interest = Principal * Rate * Time
    total_interest = principal * (annual_interest_rate / 100.0) * (months / 12.0)
    total_amount = principal + total_interest
    monthly_installment = total_amount / months if months > 0 else 0
    monthly_interest = total_interest / months if months > 0 else 0
    
    return {
        "total_interest": total_interest,
        "monthly_interest": monthly_interest,
        "total_amount": total_amount,
        "monthly_installment": monthly_installment
    }

def generate_reducing_balance_schedule(principal, annual_interest_rate, months, start_date):
    """
    Generate repayment schedule for reducing balance loans.
    
    Args:
        principal (float): Loan principal amount
        annual_interest_rate (float): Annual interest rate as percentage
        months (int): Loan period in months
        start_date (str): Start date for first installment (YYYY-MM-DD)
        
    Returns:
        list: List of schedule rows with installment details
    """
    emi = calculate_emi(principal, annual_interest_rate, months)
    monthly_rate = flt(annual_interest_rate) / 100.0 / 12.0
    outstanding = principal
    date = start_date
    schedule = []
    
    for i in range(1, months + 1):
        interest = outstanding * monthly_rate
        principal_component = emi - interest
        outstanding -= principal_component
        
        # Ensure the final balance is exactly 0
        if i == months:
            principal_component += outstanding  # Adjust for rounding
            outstanding = 0
            
        schedule.append({
            "installment_no": i,
            "due_date": date,
            "principal_component": round(principal_component, 2),
            "interest_component": round(interest, 2),
            "total_payment": round(emi, 2),
            "loan_balance": round(max(0, outstanding), 2),  # Ensure no negative balance
            "status": "Pending"
        })
        
        date = add_months(date, 1)
        
    return schedule

def generate_flat_rate_schedule(principal, annual_interest_rate, months, start_date):
    """
    Generate repayment schedule for flat rate loans.
    
    Args:
        principal (float): Loan principal amount
        annual_interest_rate (float): Annual interest rate as percentage
        months (int): Loan period in months
        start_date (str): Start date for first installment (YYYY-MM-DD)
        
    Returns:
        list: List of schedule rows with installment details
    """
    calc = calculate_flat_interest(principal, annual_interest_rate, months)
    principal_component = principal / months if months > 0 else 0
    interest_component = calc["monthly_interest"]
    monthly_payment = calc["monthly_installment"]
    outstanding = principal
    date = start_date
    schedule = []
    
    for i in range(1, months + 1):
        outstanding -= principal_component
        
        # Ensure the final balance is exactly 0
        if i == months:
            outstanding = 0
            
        schedule.append({
            "installment_no": i,
            "due_date": date,
            "principal_component": round(principal_component, 2),
            "interest_component": round(interest_component, 2),
            "total_payment": round(monthly_payment, 2),
            "loan_balance": round(max(0, outstanding), 2),  # Ensure no negative balance
            "status": "Pending"
        })
        
        date = add_months(date, 1)
        
    return schedule