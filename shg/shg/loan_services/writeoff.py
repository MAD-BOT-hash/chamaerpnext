"""
Loan write-off services for SHG Loan module.
Handles loan write-off processes and accounting.
"""
import frappe
from frappe.utils import flt, getdate, add_days
from typing import List, Dict, Any, Optional


def calculate_writeoff_amount(loan_doc: Any) -> Dict[str, float]:
    """
    Calculate write-off amount for a loan.
    
    Args:
        loan_doc: SHG Loan document
        
    Returns:
        Dictionary with write-off components
    """
    outstanding_principal = flt(loan_doc.outstanding_principal or loan_doc.loan_amount)
    outstanding_interest = flt(loan_doc.accrued_interest or 0)
    outstanding_penalty = flt(loan_doc.accrued_penalty or 0)
    total_outstanding = flt(outstanding_principal + outstanding_interest + outstanding_penalty, 2)
    
    return {
        "principal": outstanding_principal,
        "interest": outstanding_interest,
        "penalty": outstanding_penalty,
        "total": total_outstanding
    }


def process_loan_writeoff(
    loan_name: str,
    posting_date: Optional[str] = None,
    remarks: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process loan write-off.
    
    Args:
        loan_name: Name of the loan to write off
        posting_date: Date of write-off (default: today)
        remarks: Additional remarks
        
    Returns:
        Dictionary with write-off results
    """
    if not posting_date:
        posting_date = frappe.utils.today()
    
    # Get loan document
    loan_doc = frappe.get_doc("SHG Loan", loan_name)
    
    # Validate loan status
    if loan_doc.status == "Written Off":
        frappe.throw("Loan is already written off.")
    
    # Calculate write-off amount
    writeoff_amounts = calculate_writeoff_amount(loan_doc)
    
    if writeoff_amounts["total"] <= 0:
        frappe.throw("No outstanding balance to write off.")
    
    # Validate required accounts
    if not loan_doc.receivable_account:
        frappe.throw("Receivable account is required for loan write-off.")
    
    if not loan_doc.write_off_account:
        frappe.throw("Write-off account is required for loan write-off.")
    
    # Create GL entries for write-off
    from shg.shg.loan_services.gl import create_writeoff_gl_entries
    company = loan_doc.company or frappe.db.get_single_value("SHG Settings", "company")
    gl_entries = create_writeoff_gl_entries(
        loan_doc,
        writeoff_amounts["total"],
        posting_date,
        company
    )
    
    # Update loan document
    loan_doc.status = "Written Off"
    loan_doc.write_off_date = posting_date
    loan_doc.write_off_amount = writeoff_amounts["total"]
    loan_doc.outstanding_principal = 0
    loan_doc.accrued_interest = 0
    loan_doc.accrued_penalty = 0
    loan_doc.total_outstanding = 0
    
    # Lock further postings if enabled
    if getattr(loan_doc, "lock_on_full_payment", False):
        loan_doc.locked = 1
    
    loan_doc.save(ignore_permissions=True)
    
    # Create transaction log
    frappe.get_doc({
        "doctype": "SHG Loan Transaction",
        "loan": loan_name,
        "transaction_type": "Write-off",
        "posting_date": posting_date,
        "principal": writeoff_amounts["principal"],
        "interest": writeoff_amounts["interest"],
        "penalty": writeoff_amounts["penalty"],
        "remarks": remarks or f"Loan written off on {posting_date}"
    }).insert(ignore_permissions=True)
    
    return {
        "status": "success",
        "message": f"Loan {loan_name} written off successfully.",
        "writeoff_amount": writeoff_amounts["total"],
        "gl_entries": gl_entries
    }


def reverse_loan_writeoff(
    loan_name: str,
    posting_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Reverse a loan write-off.
    
    Args:
        loan_name: Name of the loan to reverse write-off
        posting_date: Date of reversal (default: today)
        
    Returns:
        Dictionary with reversal results
    """
    if not posting_date:
        posting_date = frappe.utils.today()
    
    # Get loan document
    loan_doc = frappe.get_doc("SHG Loan", loan_name)
    
    # Validate loan status
    if loan_doc.status != "Written Off":
        frappe.throw("Loan is not written off.")
    
    # Validate write-off amount
    if not loan_doc.write_off_amount or loan_doc.write_off_amount <= 0:
        frappe.throw("No write-off amount found.")
    
    # Reverse GL entries
    if loan_doc.write_off_gl_entry:
        from shg.shg.loan_services.gl import reverse_gl_entries
        company = loan_doc.company or frappe.db.get_single_value("SHG Settings", "company")
        reversal_entries = reverse_gl_entries(
            [loan_doc.write_off_gl_entry],
            posting_date,
            company
        )
    else:
        reversal_entries = []
    
    # Update loan document
    loan_doc.status = "Active"  # Or previous status
    loan_doc.write_off_date = None
    loan_doc.write_off_amount = 0
    loan_doc.write_off_gl_entry = None
    
    # Unlock if previously locked
    if getattr(loan_doc, "locked", False):
        loan_doc.locked = 0
    
    loan_doc.save(ignore_permissions=True)
    
    # Create transaction log
    frappe.get_doc({
        "doctype": "SHG Loan Transaction",
        "loan": loan_name,
        "transaction_type": "Write-off Reversal",
        "posting_date": posting_date,
        "amount": loan_doc.write_off_amount,
        "remarks": f"Write-off reversed on {posting_date}"
    }).insert(ignore_permissions=True)
    
    return {
        "status": "success",
        "message": f"Loan {loan_name} write-off reversed successfully.",
        "reversal_entries": reversal_entries
    }


def get_writeoff_eligible_loans() -> List[Dict[str, Any]]:
    """
    Get list of loans eligible for write-off.
    
    Returns:
        List of eligible loans with details
    """
    # Get loans that are overdue by more than 90 days
    cutoff_date = add_days(getdate(), -90)
    
    loans = frappe.get_all(
        "SHG Loan",
        filters={
            "status": ["in", ["Disbursed", "Active", "Overdue"]],
            "docstatus": 1,
            "next_due_date": ["<", cutoff_date]
        },
        fields=[
            "name", "member", "member_name", "loan_amount", 
            "outstanding_principal", "accrued_interest", "accrued_penalty",
            "next_due_date", "company"
        ]
    )
    
    eligible_loans = []
    for loan in loans:
        total_outstanding = flt(
            (loan.outstanding_principal or loan.loan_amount) +
            (loan.accrued_interest or 0) +
            (loan.accrued_penalty or 0),
            2
        )
        
        if total_outstanding > 0:
            eligible_loans.append({
                "loan": loan.name,
                "member": loan.member,
                "member_name": loan.member_name,
                "outstanding_amount": total_outstanding,
                "overdue_days": (getdate() - getdate(loan.next_due_date)).days,
                "company": loan.company
            })
    
    return eligible_loans


@frappe.whitelist()
def writeoff_loan(
    loan_name: str,
    posting_date: Optional[str] = None,
    remarks: Optional[str] = None
) -> Dict[str, Any]:
    """
    Whitelisted method to write off a loan.
    
    Args:
        loan_name: Name of the loan to write off
        posting_date: Date of write-off (default: today)
        remarks: Additional remarks
        
    Returns:
        Dictionary with write-off results
    """
    # Check permissions
    if not frappe.has_permission("SHG Loan", "write"):
        frappe.throw("Insufficient permissions to write off loan.")
    
    if not posting_date:
        posting_date = frappe.utils.today()
    
    # Process write-off
    result = process_loan_writeoff(loan_name, posting_date, remarks)
    
    return result


@frappe.whitelist()
def reverse_writeoff(
    loan_name: str,
    posting_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Whitelisted method to reverse a loan write-off.
    
    Args:
        loan_name: Name of the loan to reverse write-off
        posting_date: Date of reversal (default: today)
        
    Returns:
        Dictionary with reversal results
    """
    # Check permissions
    if not frappe.has_permission("SHG Loan", "write"):
        frappe.throw("Insufficient permissions to reverse loan write-off.")
    
    if not posting_date:
        posting_date = frappe.utils.today()
    
    # Reverse write-off
    result = reverse_loan_writeoff(loan_name, posting_date)
    
    return result