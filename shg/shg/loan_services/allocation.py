"""
Payment allocation services for SHG Loan module.
Handles allocation of payments across penalty, interest, and principal components.
"""
import frappe
from frappe.utils import flt, getdate
from typing import List, Dict, Any, Tuple, Optional


def allocate_payment_to_schedule(
    schedule: List[Dict[str, Any]],
    payment_amount: float,
    allocation_order: Optional[List[str]] = None
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Allocate payment across schedule rows based on specified order.
    
    Args:
        schedule: List of schedule rows
        payment_amount: Amount to allocate
        allocation_order: Order of allocation (default: penalty -> interest -> principal)
        
    Returns:
        Tuple of (updated_schedule, remaining_amount)
    """
    if allocation_order is None:
        allocation_order = ["penalty_due", "interest_due", "principal_due"]
    
    remaining_amount = flt(payment_amount)
    updated_schedule = []
    
    # Sort schedule by due date for proper allocation
    sorted_schedule = sorted(schedule, key=lambda x: getdate(x.get("due_date")))
    
    for row in sorted_schedule:
        if remaining_amount <= 0:
            updated_schedule.append(row)
            continue
            
        row_balance = flt(row.get("balance", 0))
        amount_paid = flt(row.get("amount_paid", 0))
        
        # Skip fully paid rows
        if row_balance <= 0:
            updated_schedule.append(row)
            continue
            
        # Calculate amount to allocate to this row
        allocate_to_row = min(remaining_amount, row_balance)
        
        # Update row payment details
        new_amount_paid = amount_paid + allocate_to_row
        new_balance = row_balance - allocate_to_row
        
        # Update row status
        if new_balance <= 0:
            status = "Paid"
        elif new_amount_paid > 0:
            status = "Partially Paid"
        else:
            # Check if overdue
            if getdate(row.get("due_date")) < getdate() and new_balance > 0:
                status = "Overdue"
            else:
                status = "Due"
        
        updated_row = row.copy()
        updated_row["amount_paid"] = flt(new_amount_paid, 2)
        updated_row["balance"] = flt(new_balance, 2)
        updated_row["status"] = status
        
        updated_schedule.append(updated_row)
        remaining_amount = flt(remaining_amount - allocate_to_row, 2)
    
    return updated_schedule, remaining_amount


def allocate_payment_by_components(
    schedule_row: Dict[str, Any],
    payment_amount: float,
    allocation_order: Optional[List[str]] = None
) -> Dict[str, float]:
    """
    Allocate payment to specific components of a schedule row.
    
    Args:
        schedule_row: Single schedule row
        payment_amount: Amount to allocate
        allocation_order: Order of allocation (default: penalty -> interest -> principal)
        
    Returns:
        Dictionary with allocated amounts for each component
    """
    if allocation_order is None:
        allocation_order = ["penalty_due", "interest_due", "principal_due"]
    
    remaining_amount = flt(payment_amount)
    allocation = {
        "penalty_paid": 0.0,
        "interest_paid": 0.0,
        "principal_paid": 0.0
    }
    
    components = {
        "penalty_due": "penalty_paid",
        "interest_due": "interest_paid",
        "principal_due": "principal_paid"
    }
    
    for component in allocation_order:
        if remaining_amount <= 0:
            break
            
        due_amount = flt(schedule_row.get(component, 0))
        paid_key = components.get(component)
        
        if due_amount > 0 and paid_key:
            allocate_amount = min(remaining_amount, due_amount)
            allocation[paid_key] = flt(allocate_amount, 2)
            remaining_amount = flt(remaining_amount - allocate_amount, 2)
    
    return allocation


def calculate_outstanding_balance(schedule: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculate outstanding balance from schedule.
    
    Args:
        schedule: List of schedule rows
        
    Returns:
        Dictionary with balance components
    """
    total_principal = 0.0
    total_interest = 0.0
    total_penalty = 0.0
    total_outstanding = 0.0
    
    for row in schedule:
        balance = flt(row.get("balance", 0))
        if balance > 0:
            total_principal += flt(row.get("principal_due", 0))
            total_interest += flt(row.get("interest_due", 0))
            total_penalty += flt(row.get("penalty_due", 0))
            total_outstanding += balance
    
    return {
        "principal_outstanding": flt(total_principal, 2),
        "interest_outstanding": flt(total_interest, 2),
        "penalty_outstanding": flt(total_penalty, 2),
        "total_outstanding": flt(total_outstanding, 2)
    }


def validate_payment_amount(
    schedule: List[Dict[str, Any]],
    payment_amount: float
) -> Tuple[bool, str]:
    """
    Validate payment amount against schedule.
    
    Args:
        schedule: List of schedule rows
        payment_amount: Payment amount to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if payment_amount <= 0:
        return False, "Payment amount must be greater than zero."
    
    outstanding = calculate_outstanding_balance(schedule)
    total_outstanding = outstanding["total_outstanding"]
    
    if payment_amount > total_outstanding:
        return False, f"Payment amount ({payment_amount}) exceeds outstanding balance ({total_outstanding})."
    
    return True, ""


@frappe.whitelist()
def process_loan_payment(
    loan_name: str,
    payment_amount: float,
    posting_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a payment for a loan.
    
    Args:
        loan_name: Name of the SHG Loan document
        payment_amount: Amount to pay
        posting_date: Date of payment (default: today)
        
    Returns:
        Dictionary with processing results
    """
    from shg.shg.loan_services.schedule import generate_schedule_for_loan
    
    if not posting_date:
        posting_date = frappe.utils.today()
    
    # Get loan document
    loan_doc = frappe.get_doc("SHG Loan", loan_name)
    
    # Generate current schedule
    schedule = generate_schedule_for_loan(loan_name)
    
    # Validate payment amount
    is_valid, error_msg = validate_payment_amount(schedule, payment_amount)
    if not is_valid:
        frappe.throw(error_msg)
    
    # Allocate payment
    updated_schedule, remaining_amount = allocate_payment_to_schedule(schedule, payment_amount)
    
    # Update loan document with new schedule
    loan_doc.repayment_schedule = []
    for row in updated_schedule:
        loan_doc.append("repayment_schedule", row)
    
    # Update loan summary fields
    outstanding = calculate_outstanding_balance(updated_schedule)
    loan_doc.outstanding_principal = outstanding["principal_outstanding"]
    loan_doc.accrued_interest = outstanding["interest_outstanding"]
    loan_doc.accrued_penalty = outstanding["penalty_outstanding"]
    loan_doc.total_outstanding = outstanding["total_outstanding"]
    
    # Update paid amounts
    original_outstanding = calculate_outstanding_balance(schedule)
    loan_doc.paid_principal = flt(original_outstanding["principal_outstanding"] - outstanding["principal_outstanding"], 2)
    loan_doc.paid_interest = flt(original_outstanding["interest_outstanding"] - outstanding["interest_outstanding"], 2)
    loan_doc.paid_penalty = flt(original_outstanding["penalty_outstanding"] - outstanding["penalty_outstanding"], 2)
    
    # Save loan document
    loan_doc.save(ignore_permissions=True)
    
    return {
        "status": "success",
        "message": f"Payment of {payment_amount} processed successfully.",
        "remaining_amount": remaining_amount,
        "outstanding_balance": outstanding["total_outstanding"]
    }