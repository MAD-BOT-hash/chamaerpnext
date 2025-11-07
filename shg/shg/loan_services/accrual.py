"""
Daily accrual services for SHG Loan module.
Handles interest and penalty accrual calculations.
"""
import frappe
from frappe.utils import flt, getdate, add_days
from typing import List, Dict, Any, Optional
from datetime import timedelta


def calculate_daily_interest(
    principal: float,
    interest_rate: float,
    days: int = 1
) -> float:
    """
    Calculate daily interest on principal amount.
    
    Args:
        principal: Principal amount
        interest_rate: Annual interest rate (percentage)
        days: Number of days to calculate interest for
        
    Returns:
        Daily interest amount
    """
    if principal <= 0 or interest_rate <= 0:
        return 0.0
    
    # Calculate daily interest rate
    daily_rate = (interest_rate / 100) / 365
    return flt(principal * daily_rate * days, 2)


def calculate_penalty(
    overdue_amount: float,
    penalty_rate: float,
    days_overdue: int
) -> float:
    """
    Calculate penalty for overdue amount.
    
    Args:
        overdue_amount: Amount that is overdue
        penalty_rate: Penalty rate (percentage)
        days_overdue: Number of days overdue
        
    Returns:
        Penalty amount
    """
    if overdue_amount <= 0 or penalty_rate <= 0 or days_overdue <= 0:
        return 0.0
    
    # Calculate daily penalty rate
    daily_penalty_rate = (penalty_rate / 100) / 365
    return flt(overdue_amount * daily_penalty_rate * days_overdue, 2)


def accrue_interest_for_loan(
    loan_doc: Any,
    posting_date: str
) -> Dict[str, Any]:
    """
    Accrue interest for a single loan.
    
    Args:
        loan_doc: SHG Loan document
        posting_date: Date to accrue interest for
        
    Returns:
        Dictionary with accrual details
    """
    accrued_interest = 0.0
    accrual_details = []
    
    # Check if auto accrual is enabled
    if not getattr(loan_doc, "auto_accrual_daily", False):
        return {"accrued_interest": 0.0, "details": []}
    
    # Check loan status
    if loan_doc.status not in ["Disbursed", "Active"]:
        return {"accrued_interest": 0.0, "details": []}
    
    # Process each schedule row
    for row in loan_doc.repayment_schedule:
        # Skip paid rows
        if row.status == "Paid":
            continue
            
        # Check if row is due (based on period_end or due_date)
        row_date = getdate(row.period_end or row.due_date)
        if getdate(posting_date) < row_date:
            continue
            
        # Calculate days since last accrual
        last_accrual_date = getattr(row, "last_interest_accrual_date", None)
        if last_accrual_date:
            days_since_accrual = (getdate(posting_date) - getdate(last_accrual_date)).days
        else:
            # First accrual - from disbursement date or period start
            start_date = getdate(loan_doc.disbursement_date or row.period_start)
            days_since_accrual = (getdate(posting_date) - start_date).days
            
        if days_since_accrual <= 0:
            continue
            
        # Calculate interest for outstanding principal
        outstanding_principal = flt(row.principal_due) - flt(row.amount_paid)
        if outstanding_principal <= 0:
            continue
            
        # Calculate interest based on interest method
        daily_interest = 0.0
        if loan_doc.interest_type == "Flat Rate":
            # For flat rate, calculate on original principal
            daily_interest = calculate_daily_interest(
                loan_doc.loan_amount, 
                loan_doc.interest_rate, 
                days_since_accrual
            )
        elif loan_doc.interest_type in ["Reducing (EMI)", "Reducing (Declining Balance)"]:
            # For reducing balance, calculate on outstanding principal
            daily_interest = calculate_daily_interest(
                outstanding_principal, 
                loan_doc.interest_rate, 
                days_since_accrual
            )
        
        if daily_interest > 0:
            accrued_interest += daily_interest
            accrual_details.append({
                "schedule_row": row.name,
                "principal": outstanding_principal,
                "days": days_since_accrual,
                "interest": daily_interest
            })
    
    return {
        "accrued_interest": flt(accrued_interest, 2),
        "details": accrual_details
    }


def accrue_penalty_for_loan(
    loan_doc: Any,
    posting_date: str
) -> Dict[str, Any]:
    """
    Accrue penalty for a single loan.
    
    Args:
        loan_doc: SHG Loan document
        posting_date: Date to accrue penalty for
        
    Returns:
        Dictionary with penalty details
    """
    accrued_penalty = 0.0
    penalty_details = []
    
    # Check if auto penalty is enabled
    if not getattr(loan_doc, "auto_penalty", False):
        return {"accrued_penalty": 0.0, "details": []}
    
    # Get penalty rate from settings
    penalty_rate = flt(frappe.db.get_single_value("SHG Settings", "default_penalty_rate") or 5.0)
    
    # Process each schedule row
    for row in loan_doc.repayment_schedule:
        # Skip paid rows
        if row.status == "Paid":
            continue
            
        # Check if row is overdue
        due_date = getdate(row.due_date)
        if getdate(posting_date) <= due_date:
            continue
            
        # Calculate days overdue
        days_overdue = (getdate(posting_date) - due_date).days
        
        # Check grace period
        grace_days = getattr(loan_doc, "grace_period_days", 0) or 0
        if days_overdue <= grace_days:
            continue
            
        # Calculate effective overdue days
        effective_days_overdue = days_overdue - grace_days
        
        # Calculate penalty on overdue amount
        overdue_amount = flt(row.balance)
        if overdue_amount <= 0:
            continue
            
        penalty = calculate_penalty(overdue_amount, penalty_rate, effective_days_overdue)
        if penalty > 0:
            accrued_penalty += penalty
            penalty_details.append({
                "schedule_row": row.name,
                "overdue_amount": overdue_amount,
                "days_overdue": effective_days_overdue,
                "penalty": penalty
            })
    
    return {
        "accrued_penalty": flt(accrued_penalty, 2),
        "details": penalty_details
    }


def run_daily_accruals(
    posting_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run daily accrual process for all active loans.
    
    Args:
        posting_date: Date to run accruals for (default: today)
        
    Returns:
        Dictionary with accrual results
    """
    if not posting_date:
        posting_date = frappe.utils.today()
    
    # Get all active loans
    loans = frappe.get_all(
        "SHG Loan",
        filters={
            "status": ["in", ["Disbursed", "Active"]],
            "docstatus": 1
        },
        fields=["name"]
    )
    
    total_interest_accrued = 0.0
    total_penalty_accrued = 0.0
    processed_loans = 0
    error_loans = []
    
    for loan in loans:
        try:
            loan_doc = frappe.get_doc("SHG Loan", loan.name)
            
            # Accrue interest
            interest_result = accrue_interest_for_loan(loan_doc, posting_date)
            total_interest_accrued += interest_result["accrued_interest"]
            
            # Accrue penalty
            penalty_result = accrue_penalty_for_loan(loan_doc, posting_date)
            total_penalty_accrued += penalty_result["accrued_penalty"]
            
            # Update loan document if there are accruals
            if interest_result["accrued_interest"] > 0 or penalty_result["accrued_penalty"] > 0:
                # Update accrued amounts
                loan_doc.accrued_interest = flt((loan_doc.accrued_interest or 0) + interest_result["accrued_interest"], 2)
                loan_doc.accrued_penalty = flt((loan_doc.accrued_penalty or 0) + penalty_result["accrued_penalty"], 2)
                loan_doc.total_outstanding = flt((loan_doc.total_outstanding or 0) + interest_result["accrued_interest"] + penalty_result["accrued_penalty"], 2)
                
                # Update last accrual date for schedule rows
                for row in loan_doc.repayment_schedule:
                    row.last_interest_accrual_date = posting_date
                
                loan_doc.save(ignore_permissions=True)
            
            processed_loans += 1
            
        except Exception as e:
            frappe.log_error(
                frappe.get_traceback(),
                f"Error processing accruals for loan {loan.name}"
            )
            error_loans.append({
                "loan": loan.name,
                "error": str(e)
            })
    
    return {
        "status": "success",
        "posting_date": posting_date,
        "processed_loans": processed_loans,
        "total_interest_accrued": flt(total_interest_accrued, 2),
        "total_penalty_accrued": flt(total_penalty_accrued, 2),
        "total_accrued": flt(total_interest_accrued + total_penalty_accrued, 2),
        "errors": error_loans
    }


@frappe.whitelist()
def process_daily_accruals(
    posting_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Whitelisted method to process daily accruals.
    
    Args:
        posting_date: Date to run accruals for (default: today)
        
    Returns:
        Dictionary with accrual results
    """
    # Check if user has permission
    if not frappe.has_permission("SHG Loan", "write"):
        frappe.throw("Insufficient permissions to process accruals.")
    
    if not posting_date:
        posting_date = frappe.utils.today()
    
    result = run_daily_accruals(posting_date)
    
    # Log the process
    frappe.get_doc({
        "doctype": "SHG Loan Transaction",
        "transaction_type": "Interest Accrual",
        "posting_date": posting_date,
        "amount": result["total_accrued"],
        "remarks": f"Daily accruals processed for {result['processed_loans']} loans"
    }).insert(ignore_permissions=True)
    
    return result