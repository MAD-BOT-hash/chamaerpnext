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
    
    if repayment_amount > loan_doc.total_outstanding_amount:
        frappe.throw(f"Repayment amount ({repayment_amount}) cannot exceed outstanding amount ({loan_doc.total_outstanding_amount})")
    
    # Create loan repayment record
    loan_repayment = frappe.new_doc("SHG Loan Repayment")
    loan_repayment.loan = loan
    loan_repayment.member = loan_doc.member
    loan_repayment.posting_date = posting_date
    loan_repayment.amount = repayment_amount
    loan_repayment.company = company or loan_doc.company
    loan_repayment.principal_amount = repayment_amount
    loan_repayment.interest_amount = 0.0  # Interest calculation logic would go here if needed
    
    loan_repayment.save()
    loan_repayment.submit()
    
    # Update loan outstanding amount
    update_loan_outstanding_amount(loan)
    
    # Update repayment schedule
    update_repayment_schedule(loan, repayment_amount)
    
    return {
        "success": True,
        "loan_repayment": loan_repayment.name,
        "message": f"Successfully processed repayment of {repayment_amount} for loan {loan}"
    }

def update_loan_outstanding_amount(loan):
    """
    Update the outstanding amount on the loan document
    
    Args:
        loan (str): Loan document name
    """
    # Calculate outstanding amount based on repayments
    total_disbursed = frappe.db.get_value("SHG Loan", loan, "total_disbursed_amount") or 0
    total_repaid = frappe.db.sql("""
        SELECT SUM(amount) as total_repaid
        FROM `tabSHG Loan Repayment`
        WHERE loan = %s AND docstatus = 1
    """, (loan,), as_dict=True)[0].total_repaid or 0
    
    outstanding_amount = total_disbursed - total_repaid
    
    # Update loan document
    frappe.db.set_value("SHG Loan", loan, "total_outstanding_amount", outstanding_amount)
    
    # Update loan status based on outstanding amount
    if outstanding_amount <= 0:
        frappe.db.set_value("SHG Loan", loan, "status", "Closed")
    elif total_repaid > 0:
        frappe.db.set_value("SHG Loan", loan, "status", "Partially Paid")

def update_repayment_schedule(loan, repayment_amount):
    """
    Update the repayment schedule based on the repayment amount
    
    Args:
        loan (str): Loan document name
        repayment_amount (float): Amount that was repaid
    """
    # Get all pending installments sorted by due date
    installments = frappe.db.sql("""
        SELECT name, due_date, unpaid_balance, paid_amount, status
        FROM `tabSHG Loan Repayment Schedule`
        WHERE parent = %s
        ORDER BY due_date ASC
    """, (loan,), as_dict=True)
    
    remaining_amount = repayment_amount
    
    for installment in installments:
        if remaining_amount <= 0:
            break
            
        if installment.status in ["Paid", "Closed"]:
            continue
            
        # Calculate how much of this installment can be paid
        installment_payment = min(installment.unpaid_balance, remaining_amount)
        
        # Update the installment
        schedule_doc = frappe.get_doc("SHG Loan Repayment Schedule", installment.name)
        schedule_doc.paid_amount = (schedule_doc.paid_amount or 0) + installment_payment
        schedule_doc.unpaid_balance = (schedule_doc.unpaid_balance or 0) - installment_payment
        
        if schedule_doc.unpaid_balance <= 0:
            schedule_doc.status = "Paid"
        else:
            schedule_doc.status = "Partially Paid"
            
        schedule_doc.save(ignore_permissions=True)
        
        remaining_amount -= installment_payment

def get_outstanding_amount(loan):
    """
    Get the current outstanding amount for a loan
    
    Args:
        loan (str): Loan document name
    
    Returns:
        float: Outstanding amount
    """
    loan_doc = frappe.get_doc("SHG Loan", loan)
    return loan_doc.total_outstanding_amount or 0

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