import frappe
from frappe.utils import flt, today
from datetime import datetime

def process_loan_repayment(loan, repayment_amount, posting_date=None, company=None):
    """
    Process a single loan repayment
    
    Args:
        loan (str): Loan document name
        repayment_amount (float): Amount to be repaid
        posting_date (str): Date of repayment
        company (str): Company name
    
    Returns:
        dict: Result of the repayment processing
    """
    if not posting_date:
        posting_date = today()
    
    # Get loan details
    loan_doc = frappe.get_doc("SHG Loan", loan)
    
    # Validate repayment amount
    if repayment_amount <= 0:
        frappe.throw("Repayment amount must be greater than zero")
    
    current_balance = flt(getattr(loan_doc, "balance_amount", None) or getattr(loan_doc, "loan_balance", 0))
    if repayment_amount > current_balance:
        frappe.throw(f"Repayment amount ({repayment_amount}) cannot exceed outstanding amount ({current_balance})")
    
    # Create loan repayment record
    loan_repayment = frappe.new_doc("SHG Loan Repayment")
    loan_repayment.loan = loan
    loan_repayment.member = loan_doc.member
    loan_repayment.posting_date = posting_date
    loan_repayment.repayment_date = posting_date
    loan_repayment.total_paid = repayment_amount
    loan_repayment.company = company or loan_doc.company
    
    loan_repayment.insert(ignore_permissions=True)
    loan_repayment.submit()
    
    return {
        "success": True,
        "loan_repayment": loan_repayment.name,
        "message": f"Successfully processed repayment of {repayment_amount} for loan {loan}"
    }

def get_outstanding_amount(loan):
    """
    Get the current outstanding amount for a loan
    
    Args:
        loan (str): Loan document name
    
    Returns:
        float: Outstanding amount
    """
    loan_doc = frappe.get_doc("SHG Loan", loan)
    return flt(getattr(loan_doc, "balance_amount", None) or getattr(loan_doc, "loan_balance", 0))

def validate_member_active(member):
    """
    Validate if a member is active
    
    Args:
        member (str): Member document name
    
    Returns:
        bool: True if member is active, False otherwise
    """
    status = frappe.db.get_value("SHG Member", member, "status")
    return status == "Active"

def validate_loan_active(loan):
    """
    Validate if a loan is active (not cancelled or closed)
    
    Args:
        loan (str): Loan document name
    
    Returns:
        bool: True if loan is active, False otherwise
    """
    status = frappe.db.get_value("SHG Loan", loan, "status")
    return status in ["Disbursed", "Partially Paid"]