"""
Loan schedule generation services for SHG Loan module.
Supports Flat, Reducing (EMI), and Reducing (Declining Balance) interest methods.
"""
import frappe
from frappe.utils import flt, getdate, add_months
from typing import List, Dict, Any


def build_flat_rate_schedule(
    principal: float,
    interest_rate: float,
    term_months: int,
    repayment_frequency: str = "Monthly",
    grace_period_installments: int = 0
) -> List[Dict[str, Any]]:
    """
    Generate a flat rate repayment schedule.
    
    Args:
        principal: Loan principal amount
        interest_rate: Annual interest rate (percentage)
        term_months: Loan term in months
        repayment_frequency: Frequency of repayments
        grace_period_installments: Number of grace period installments
        
    Returns:
        List of schedule rows with repayment details
    """
    if not principal or not interest_rate or not term_months:
        return []
        
    schedule = []
    
    # Calculate frequency multiplier
    freq_multiplier = _get_frequency_multiplier(repayment_frequency)
    
    # Calculate total interest for flat rate
    total_interest = principal * (interest_rate / 100) * (term_months / 12)
    total_amount = principal + total_interest
    emi = total_amount / term_months
    
    # For flat rate, principal and interest components are fixed
    monthly_interest = total_interest / term_months
    monthly_principal = principal / term_months
    
    # Generate schedule rows
    for i in range(1, term_months + 1):
        # Skip grace period installments
        if i <= grace_period_installments:
            continue
            
        due_date = add_months(getdate(), (i - 1) * freq_multiplier)
        
        schedule.append({
            "installment_no": i,
            "period_start": add_months(getdate(), (i - 1) * freq_multiplier),
            "period_end": add_months(getdate(), i * freq_multiplier),
            "due_date": due_date,
            "principal_due": flt(monthly_principal, 2),
            "interest_due": flt(monthly_interest, 2),
            "penalty_due": 0.0,
            "total_due": flt(emi, 2),
            "amount_paid": 0.0,
            "balance": flt(emi, 2),
            "status": "Due"
        })
    
    # Adjust last installment for rounding
    if schedule:
        _adjust_last_installment(schedule, principal, total_interest)
    
    return schedule


def build_reducing_balance_emi_schedule(
    principal: float,
    interest_rate: float,
    term_months: int,
    repayment_frequency: str = "Monthly",
    grace_period_installments: int = 0
) -> List[Dict[str, Any]]:
    """
    Generate a reducing balance EMI repayment schedule.
    
    Args:
        principal: Loan principal amount
        interest_rate: Annual interest rate (percentage)
        term_months: Loan term in months
        repayment_frequency: Frequency of repayments
        grace_period_installments: Number of grace period installments
        
    Returns:
        List of schedule rows with repayment details
    """
    if not principal or not interest_rate or not term_months:
        return []
        
    schedule = []
    
    # Calculate frequency multiplier
    freq_multiplier = _get_frequency_multiplier(repayment_frequency)
    
    # Calculate monthly interest rate
    monthly_rate = (interest_rate / 100) / 12
    
    # Calculate EMI using annuity formula
    if monthly_rate > 0:
        emi = principal * (monthly_rate * (1 + monthly_rate) ** term_months) / ((1 + monthly_rate) ** term_months - 1)
    else:
        emi = principal / term_months
    
    remaining_principal = principal
    
    # Generate schedule rows
    for i in range(1, term_months + 1):
        # Skip grace period installments
        if i <= grace_period_installments:
            continue
            
        due_date = add_months(getdate(), (i - 1) * freq_multiplier)
        
        # Calculate interest for the period
        interest_component = remaining_principal * monthly_rate
        principal_component = emi - interest_component
        remaining_principal -= principal_component
        
        schedule.append({
            "installment_no": i,
            "period_start": add_months(getdate(), (i - 1) * freq_multiplier),
            "period_end": add_months(getdate(), i * freq_multiplier),
            "due_date": due_date,
            "principal_due": flt(principal_component, 2),
            "interest_due": flt(interest_component, 2),
            "penalty_due": 0.0,
            "total_due": flt(emi, 2),
            "amount_paid": 0.0,
            "balance": flt(emi, 2),
            "status": "Due"
        })
    
    # Adjust last installment for rounding
    if schedule:
        _adjust_last_installment(schedule, principal, emi * term_months - principal)
    
    return schedule


def build_reducing_balance_declining_schedule(
    principal: float,
    interest_rate: float,
    term_months: int,
    repayment_frequency: str = "Monthly",
    grace_period_installments: int = 0
) -> List[Dict[str, Any]]:
    """
    Generate a reducing balance declining schedule.
    
    Args:
        principal: Loan principal amount
        interest_rate: Annual interest rate (percentage)
        term_months: Loan term in months
        repayment_frequency: Frequency of repayments
        grace_period_installments: Number of grace period installments
        
    Returns:
        List of schedule rows with repayment details
    """
    if not principal or not interest_rate or not term_months:
        return []
        
    schedule = []
    
    # Calculate frequency multiplier
    freq_multiplier = _get_frequency_multiplier(repayment_frequency)
    
    # Calculate monthly interest rate
    monthly_rate = (interest_rate / 100) / 12
    
    # For declining balance, we calculate principal per installment
    monthly_principal = principal / term_months
    remaining_principal = principal
    
    # Generate schedule rows
    for i in range(1, term_months + 1):
        # Skip grace period installments
        if i <= grace_period_installments:
            continue
            
        due_date = add_months(getdate(), (i - 1) * freq_multiplier)
        
        # Calculate interest for the period on remaining principal
        interest_component = remaining_principal * monthly_rate
        principal_component = monthly_principal
        total_due = principal_component + interest_component
        remaining_principal -= principal_component
        
        schedule.append({
            "installment_no": i,
            "period_start": add_months(getdate(), (i - 1) * freq_multiplier),
            "period_end": add_months(getdate(), i * freq_multiplier),
            "due_date": due_date,
            "principal_due": flt(principal_component, 2),
            "interest_due": flt(interest_component, 2),
            "penalty_due": 0.0,
            "total_due": flt(total_due, 2),
            "amount_paid": 0.0,
            "balance": flt(total_due, 2),
            "status": "Due"
        })
    
    # Adjust last installment for rounding
    if schedule:
        total_interest = sum(row["interest_due"] for row in schedule)
        _adjust_last_installment(schedule, principal, total_interest)
    
    return schedule


def _get_frequency_multiplier(frequency: str) -> int:
    """Get frequency multiplier for repayment calculations."""
    multipliers = {
        "Daily": 1,
        "Weekly": 7,
        "Bi-Weekly": 14,
        "Monthly": 1,
        "Bi-Monthly": 2,
        "Quarterly": 3,
        "Yearly": 12
    }
    return multipliers.get(frequency, 1)


def _adjust_last_installment(schedule: List[Dict], principal: float, total_interest: float):
    """
    Adjust the last installment to ensure totals match principal and interest.
    
    Args:
        schedule: List of schedule rows
        principal: Original principal amount
        total_interest: Total interest calculated
    """
    if not schedule:
        return
        
    # Calculate actual totals
    actual_principal = sum(row["principal_due"] for row in schedule)
    actual_interest = sum(row["interest_due"] for row in schedule)
    
    # Calculate differences
    principal_diff = principal - actual_principal
    interest_diff = total_interest - actual_interest
    
    # Adjust last installment
    last_row = schedule[-1]
    last_row["principal_due"] = flt(last_row["principal_due"] + principal_diff, 2)
    last_row["interest_due"] = flt(last_row["interest_due"] + interest_diff, 2)
    last_row["total_due"] = flt(last_row["principal_due"] + last_row["interest_due"], 2)
    last_row["balance"] = flt(last_row["total_due"], 2)


def validate_schedule_totals(schedule: List[Dict], principal: float, tolerance: float = 0.01) -> bool:
    """
    Validate that schedule totals match expected principal.
    
    Args:
        schedule: List of schedule rows
        principal: Expected principal amount
        tolerance: Acceptable difference due to rounding
        
    Returns:
        True if totals are valid, False otherwise
    """
    if not schedule:
        return False
        
    total_principal = sum(row["principal_due"] for row in schedule)
    return abs(total_principal - principal) <= tolerance


@frappe.whitelist()
def generate_schedule_for_loan(loan_name: str) -> List[Dict[str, Any]]:
    """
    Generate repayment schedule for a loan document.
    
    Args:
        loan_name: Name of the SHG Loan document
        
    Returns:
        List of schedule rows
    """
    loan_doc = frappe.get_doc("SHG Loan", loan_name)
    
    # Validate required fields
    if not loan_doc.loan_amount or not loan_doc.interest_rate or not loan_doc.loan_period_months:
        frappe.throw("Loan amount, interest rate, and loan period are required to generate schedule.")
    
    # Generate schedule based on interest method
    schedule = []
    if loan_doc.interest_type == "Flat Rate":
        schedule = build_flat_rate_schedule(
            loan_doc.loan_amount,
            loan_doc.interest_rate,
            loan_doc.loan_period_months,
            loan_doc.repayment_frequency,
            getattr(loan_doc, "grace_period_installments", 0)
        )
    elif loan_doc.interest_type == "Reducing (EMI)":
        schedule = build_reducing_balance_emi_schedule(
            loan_doc.loan_amount,
            loan_doc.interest_rate,
            loan_doc.loan_period_months,
            loan_doc.repayment_frequency,
            getattr(loan_doc, "grace_period_installments", 0)
        )
    elif loan_doc.interest_type == "Reducing (Declining Balance)":
        schedule = build_reducing_balance_declining_schedule(
            loan_doc.loan_amount,
            loan_doc.interest_rate,
            loan_doc.loan_period_months,
            loan_doc.repayment_frequency,
            getattr(loan_doc, "grace_period_installments", 0)
        )
    else:
        frappe.throw(f"Unsupported interest type: {loan_doc.interest_type}")
    
    # Validate schedule
    if not validate_schedule_totals(schedule, loan_doc.loan_amount):
        frappe.throw("Generated schedule totals do not match loan principal.")
    
    return schedule