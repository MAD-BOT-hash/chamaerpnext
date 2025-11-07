"""
Loan rescheduling services for SHG Loan module.
Handles loan rescheduling and amendment flows.
"""
import frappe
from frappe.utils import flt, getdate
from typing import List, Dict, Any, Tuple


def create_reschedule_amendment(
    original_loan_name: str,
    new_terms: Dict[str, Any]
) -> str:
    """
    Create a reschedule amendment for a loan.
    
    Args:
        original_loan_name: Name of the original loan
        new_terms: Dictionary with new loan terms
        
    Returns:
        Name of the new rescheduled loan
    """
    # Get original loan document
    original_loan = frappe.get_doc("SHG Loan", original_loan_name)
    
    # Validate loan status
    if original_loan.status not in ["Disbursed", "Active"]:
        frappe.throw("Only active loans can be rescheduled.")
    
    # Calculate outstanding balance
    outstanding_principal = flt(original_loan.outstanding_principal or original_loan.loan_amount)
    outstanding_interest = flt(original_loan.accrued_interest or 0)
    outstanding_penalty = flt(original_loan.accrued_penalty or 0)
    total_outstanding = flt(outstanding_principal + outstanding_interest + outstanding_penalty, 2)
    
    if total_outstanding <= 0:
        frappe.throw("No outstanding balance to reschedule.")
    
    # Create new loan document for reschedule
    new_loan = frappe.get_doc({
        "doctype": "SHG Loan",
        "naming_series": original_loan.naming_series,
        "member": original_loan.member,
        "member_name": original_loan.member_name,
        "company": original_loan.company,
        "loan_type": original_loan.loan_type,
        "loan_amount": outstanding_principal,
        "interest_rate": new_terms.get("interest_rate", original_loan.interest_rate),
        "interest_type": new_terms.get("interest_type", original_loan.interest_type),
        "loan_period_months": new_terms.get("loan_period_months", original_loan.loan_period_months),
        "repayment_frequency": new_terms.get("repayment_frequency", original_loan.repayment_frequency),
        "grace_period_installments": new_terms.get("grace_period_installments", 0),
        "application_date": getdate(),
        "approval_date": getdate(),
        "disbursement_date": getdate(),
        "repayment_start_date": new_terms.get("repayment_start_date", getdate()),
        "status": "Approved",
        "parent_loan": original_loan_name,
        "is_rescheduled": 1,
        # Copy account mappings
        "receivable_account": original_loan.receivable_account,
        "interest_income_account": original_loan.interest_income_account,
        "penalty_income_account": original_loan.penalty_income_account,
        "disbursement_account": original_loan.disbursement_account,
        "write_off_account": original_loan.write_off_account
    })
    
    # Insert new loan
    new_loan.insert(ignore_permissions=True)
    new_loan.submit()
    
    # Generate repayment schedule for new loan
    from shg.shg.loan_services.schedule import generate_schedule_for_loan
    schedule = generate_schedule_for_loan(new_loan.name)
    
    # Add schedule to new loan
    for row in schedule:
        new_loan.append("repayment_schedule", row)
    
    new_loan.save(ignore_permissions=True)
    
    # Close original loan
    original_loan.status = "Rescheduled"
    original_loan.save(ignore_permissions=True)
    
    # Create transaction log
    frappe.get_doc({
        "doctype": "SHG Loan Transaction",
        "loan": original_loan_name,
        "transaction_type": "Reschedule",
        "posting_date": getdate(),
        "principal": outstanding_principal,
        "interest": outstanding_interest,
        "penalty": outstanding_penalty,
        "remarks": f"Loan rescheduled to {new_loan.name}"
    }).insert(ignore_permissions=True)
    
    # Create transaction log for new loan
    frappe.get_doc({
        "doctype": "SHG Loan Transaction",
        "loan": new_loan.name,
        "transaction_type": "Reschedule",
        "posting_date": getdate(),
        "principal": outstanding_principal,
        "interest": outstanding_interest,
        "penalty": outstanding_penalty,
        "remarks": f"Loan created from reschedule of {original_loan_name}"
    }).insert(ignore_permissions=True)
    
    return new_loan.name


def validate_reschedule_terms(
    original_loan: Any,
    new_terms: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Validate reschedule terms.
    
    Args:
        original_loan: Original loan document
        new_terms: New terms to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Validate required fields
    required_fields = ["interest_rate", "loan_period_months", "repayment_start_date"]
    for field in required_fields:
        if field not in new_terms or new_terms[field] is None:
            return False, f"Required field {field} is missing."
    
    # Validate interest rate
    if flt(new_terms["interest_rate"]) <= 0:
        return False, "Interest rate must be greater than zero."
    
    # Validate loan period
    if int(new_terms["loan_period_months"]) <= 0:
        return False, "Loan period must be greater than zero."
    
    # Validate repayment start date
    if getdate(new_terms["repayment_start_date"]) <= getdate():
        return False, "Repayment start date must be in the future."
    
    # Validate interest type
    valid_interest_types = ["Flat Rate", "Reducing (EMI)", "Reducing (Declining Balance)"]
    if new_terms.get("interest_type") not in valid_interest_types:
        return False, f"Invalid interest type. Must be one of: {', '.join(valid_interest_types)}"
    
    return True, ""


def calculate_reschedule_impact(
    original_loan_name: str,
    new_terms: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate the impact of rescheduling a loan.
    
    Args:
        original_loan_name: Name of the original loan
        new_terms: New loan terms
        
    Returns:
        Dictionary with reschedule impact details
    """
    original_loan = frappe.get_doc("SHG Loan", original_loan_name)
    
    # Calculate current outstanding
    outstanding_principal = flt(original_loan.outstanding_principal or original_loan.loan_amount)
    outstanding_interest = flt(original_loan.accrued_interest or 0)
    outstanding_penalty = flt(original_loan.accrued_penalty or 0)
    total_outstanding = flt(outstanding_principal + outstanding_interest + outstanding_penalty, 2)
    
    # Calculate new EMI based on new terms
    from shg.shg.loan_services.schedule import build_reducing_balance_emi_schedule
    new_schedule = build_reducing_balance_emi_schedule(
        outstanding_principal,
        flt(new_terms.get("interest_rate", original_loan.interest_rate)),
        int(new_terms.get("loan_period_months", original_loan.loan_period_months)),
        new_terms.get("repayment_frequency", original_loan.repayment_frequency),
        int(new_terms.get("grace_period_installments", 0))
    )
    
    new_emi = new_schedule[0]["total_due"] if new_schedule else 0
    total_new_repayment = sum(row["total_due"] for row in new_schedule)
    
    # Calculate savings/extra cost
    difference = flt(total_new_repayment - total_outstanding, 2)
    
    return {
        "original_outstanding": total_outstanding,
        "original_principal": outstanding_principal,
        "original_interest": outstanding_interest,
        "original_penalty": outstanding_penalty,
        "new_total_repayment": flt(total_new_repayment, 2),
        "new_emi": flt(new_emi, 2),
        "difference": difference,
        "savings": difference < 0,
        "extra_cost": difference > 0
    }


@frappe.whitelist()
def reschedule_loan(
    original_loan_name: str,
    new_terms: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Whitelisted method to reschedule a loan.
    
    Args:
        original_loan_name: Name of the original loan
        new_terms: Dictionary with new loan terms
        
    Returns:
        Dictionary with reschedule results
    """
    # Check permissions
    if not frappe.has_permission("SHG Loan", "write"):
        frappe.throw("Insufficient permissions to reschedule loan.")
    
    # Get original loan
    original_loan = frappe.get_doc("SHG Loan", original_loan_name)
    
    # Validate reschedule terms
    is_valid, error_msg = validate_reschedule_terms(original_loan, new_terms)
    if not is_valid:
        frappe.throw(error_msg)
    
    # Calculate impact
    impact = calculate_reschedule_impact(original_loan_name, new_terms)
    
    # Create reschedule amendment
    new_loan_name = create_reschedule_amendment(original_loan_name, new_terms)
    
    return {
        "status": "success",
        "message": f"Loan rescheduled successfully. New loan: {new_loan_name}",
        "new_loan": new_loan_name,
        "impact": impact
    }