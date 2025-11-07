"""
GL (General Ledger) posting services for SHG Loan module.
Handles creation of GL entries for loan transactions.
"""
import frappe
from frappe.utils import flt, getdate
from typing import List, Dict, Any, Optional


def create_disbursement_gl_entries(
    loan_doc: Any,
    posting_date: str,
    company: str
) -> List[str]:
    """
    Create GL entries for loan disbursement.
    
    Args:
        loan_doc: SHG Loan document
        posting_date: Date of disbursement
        company: Company name
        
    Returns:
        List of created GL entry names
    """
    gl_entries = []
    
    # Validate required accounts
    if not loan_doc.receivable_account:
        frappe.throw("Receivable account is required for loan disbursement.")
    
    if not loan_doc.disbursement_account:
        frappe.throw("Disbursement account is required for loan disbursement.")
    
    # Dr Loans Receivable (Asset increases)
    gl_entry = frappe.get_doc({
        "doctype": "GL Entry",
        "posting_date": posting_date,
        "account": loan_doc.receivable_account,
        "debit": flt(loan_doc.loan_amount, 2),
        "credit": 0,
        "against": loan_doc.disbursement_account,
        "party_type": "SHG Member",
        "party": loan_doc.member,
        "voucher_type": "SHG Loan",
        "voucher_no": loan_doc.name,
        "company": company,
        "remarks": f"Loan disbursement for {loan_doc.name}"
    })
    gl_entry.insert(ignore_permissions=True)
    gl_entry.submit()
    gl_entries.append(gl_entry.name)
    
    # Cr Bank/Cash (Asset decreases or liability increases)
    gl_entry = frappe.get_doc({
        "doctype": "GL Entry",
        "posting_date": posting_date,
        "account": loan_doc.disbursement_account,
        "debit": 0,
        "credit": flt(loan_doc.loan_amount, 2),
        "against": loan_doc.receivable_account,
        "party_type": "SHG Member",
        "party": loan_doc.member,
        "voucher_type": "SHG Loan",
        "voucher_no": loan_doc.name,
        "company": company,
        "remarks": f"Loan disbursement for {loan_doc.name}"
    })
    gl_entry.insert(ignore_permissions=True)
    gl_entry.submit()
    gl_entries.append(gl_entry.name)
    
    return gl_entries


def create_repayment_gl_entries(
    loan_doc: Any,
    repayment_amount: float,
    principal_paid: float,
    interest_paid: float,
    penalty_paid: float,
    posting_date: str,
    company: str,
    bank_cash_account: str
) -> List[str]:
    """
    Create GL entries for loan repayment.
    
    Args:
        loan_doc: SHG Loan document
        repayment_amount: Total repayment amount
        principal_paid: Principal component paid
        interest_paid: Interest component paid
        penalty_paid: Penalty component paid
        posting_date: Date of repayment
        company: Company name
        bank_cash_account: Bank/Cash account for receipt
        
    Returns:
        List of created GL entry names
    """
    gl_entries = []
    total_allocated = flt(principal_paid + interest_paid + penalty_paid, 2)
    
    # Validate that allocation matches repayment amount
    if abs(repayment_amount - total_allocated) > 0.01:
        frappe.throw(f"Repayment allocation mismatch: {repayment_amount} vs {total_allocated}")
    
    # Validate required accounts
    if not loan_doc.receivable_account:
        frappe.throw("Receivable account is required for loan repayment.")
    
    if not loan_doc.interest_income_account and interest_paid > 0:
        frappe.throw("Interest income account is required for interest repayment.")
    
    if not loan_doc.penalty_income_account and penalty_paid > 0:
        frappe.throw("Penalty income account is required for penalty repayment.")
    
    # Dr Bank/Cash (Asset increases)
    if repayment_amount > 0:
        gl_entry = frappe.get_doc({
            "doctype": "GL Entry",
            "posting_date": posting_date,
            "account": bank_cash_account,
            "debit": flt(repayment_amount, 2),
            "credit": 0,
            "against": loan_doc.member,
            "party_type": "SHG Member",
            "party": loan_doc.member,
            "voucher_type": "SHG Loan Repayment",
            "voucher_no": f"LR-{loan_doc.name}-{posting_date}",
            "company": company,
            "remarks": f"Loan repayment for {loan_doc.name}"
        })
        gl_entry.insert(ignore_permissions=True)
        gl_entry.submit()
        gl_entries.append(gl_entry.name)
    
    # Cr Loans Receivable (Asset decreases)
    if principal_paid > 0:
        gl_entry = frappe.get_doc({
            "doctype": "GL Entry",
            "posting_date": posting_date,
            "account": loan_doc.receivable_account,
            "debit": 0,
            "credit": flt(principal_paid, 2),
            "against": loan_doc.member,
            "party_type": "SHG Member",
            "party": loan_doc.member,
            "voucher_type": "SHG Loan Repayment",
            "voucher_no": f"LR-{loan_doc.name}-{posting_date}",
            "company": company,
            "remarks": f"Principal repayment for {loan_doc.name}"
        })
        gl_entry.insert(ignore_permissions=True)
        gl_entry.submit()
        gl_entries.append(gl_entry.name)
    
    # Cr Interest Income (Income increases)
    if interest_paid > 0:
        gl_entry = frappe.get_doc({
            "doctype": "GL Entry",
            "posting_date": posting_date,
            "account": loan_doc.interest_income_account,
            "debit": 0,
            "credit": flt(interest_paid, 2),
            "against": loan_doc.member,
            "party_type": "SHG Member",
            "party": loan_doc.member,
            "voucher_type": "SHG Loan Repayment",
            "voucher_no": f"LR-{loan_doc.name}-{posting_date}",
            "company": company,
            "remarks": f"Interest repayment for {loan_doc.name}"
        })
        gl_entry.insert(ignore_permissions=True)
        gl_entry.submit()
        gl_entries.append(gl_entry.name)
    
    # Cr Penalty Income (Income increases)
    if penalty_paid > 0:
        gl_entry = frappe.get_doc({
            "doctype": "GL Entry",
            "posting_date": posting_date,
            "account": loan_doc.penalty_income_account,
            "debit": 0,
            "credit": flt(penalty_paid, 2),
            "against": loan_doc.member,
            "party_type": "SHG Member",
            "party": loan_doc.member,
            "voucher_type": "SHG Loan Repayment",
            "voucher_no": f"LR-{loan_doc.name}-{posting_date}",
            "company": company,
            "remarks": f"Penalty repayment for {loan_doc.name}"
        })
        gl_entry.insert(ignore_permissions=True)
        gl_entry.submit()
        gl_entries.append(gl_entry.name)
    
    return gl_entries


def create_interest_accrual_gl_entries(
    loan_doc: Any,
    accrued_interest: float,
    posting_date: str,
    company: str
) -> List[str]:
    """
    Create GL entries for interest accrual.
    
    Args:
        loan_doc: SHG Loan document
        accrued_interest: Amount of interest accrued
        posting_date: Date of accrual
        company: Company name
        
    Returns:
        List of created GL entry names
    """
    gl_entries = []
    
    # Validate required accounts
    if not loan_doc.receivable_account:
        frappe.throw("Receivable account is required for interest accrual.")
    
    if not loan_doc.interest_income_account:
        frappe.throw("Interest income account is required for interest accrual.")
    
    # Dr Interest Receivable (Asset increases)
    gl_entry = frappe.get_doc({
        "doctype": "GL Entry",
        "posting_date": posting_date,
        "account": f"Interest Receivable - {loan_doc.receivable_account.split(' - ')[0]}",
        "debit": flt(accrued_interest, 2),
        "credit": 0,
        "against": loan_doc.member,
        "party_type": "SHG Member",
        "party": loan_doc.member,
        "voucher_type": "SHG Loan Interest Accrual",
        "voucher_no": f"LIA-{loan_doc.name}-{posting_date}",
        "company": company,
        "remarks": f"Interest accrual for {loan_doc.name}"
    })
    gl_entry.insert(ignore_permissions=True)
    gl_entry.submit()
    gl_entries.append(gl_entry.name)
    
    # Cr Interest Income (Income increases)
    gl_entry = frappe.get_doc({
        "doctype": "GL Entry",
        "posting_date": posting_date,
        "account": loan_doc.interest_income_account,
        "debit": 0,
        "credit": flt(accrued_interest, 2),
        "against": loan_doc.member,
        "party_type": "SHG Member",
        "party": loan_doc.member,
        "voucher_type": "SHG Loan Interest Accrual",
        "voucher_no": f"LIA-{loan_doc.name}-{posting_date}",
        "company": company,
        "remarks": f"Interest accrual for {loan_doc.name}"
    })
    gl_entry.insert(ignore_permissions=True)
    gl_entry.submit()
    gl_entries.append(gl_entry.name)
    
    return gl_entries


def create_penalty_accrual_gl_entries(
    loan_doc: Any,
    accrued_penalty: float,
    posting_date: str,
    company: str
) -> List[str]:
    """
    Create GL entries for penalty accrual.
    
    Args:
        loan_doc: SHG Loan document
        accrued_penalty: Amount of penalty accrued
        posting_date: Date of accrual
        company: Company name
        
    Returns:
        List of created GL entry names
    """
    gl_entries = []
    
    # Validate required accounts
    if not loan_doc.penalty_income_account:
        frappe.throw("Penalty income account is required for penalty accrual.")
    
    # Cr Penalty Income (Income increases)
    gl_entry = frappe.get_doc({
        "doctype": "GL Entry",
        "posting_date": posting_date,
        "account": loan_doc.penalty_income_account,
        "debit": 0,
        "credit": flt(accrued_penalty, 2),
        "against": loan_doc.member,
        "party_type": "SHG Member",
        "party": loan_doc.member,
        "voucher_type": "SHG Loan Penalty Accrual",
        "voucher_no": f"LPA-{loan_doc.name}-{posting_date}",
        "company": company,
        "remarks": f"Penalty accrual for {loan_doc.name}"
    })
    gl_entry.insert(ignore_permissions=True)
    gl_entry.submit()
    gl_entries.append(gl_entry.name)
    
    return gl_entries


def create_writeoff_gl_entries(
    loan_doc: Any,
    writeoff_amount: float,
    posting_date: str,
    company: str
) -> List[str]:
    """
    Create GL entries for loan write-off.
    
    Args:
        loan_doc: SHG Loan document
        writeoff_amount: Amount to write off
        posting_date: Date of write-off
        company: Company name
        
    Returns:
        List of created GL entry names
    """
    gl_entries = []
    
    # Validate required accounts
    if not loan_doc.receivable_account:
        frappe.throw("Receivable account is required for loan write-off.")
    
    if not loan_doc.write_off_account:
        frappe.throw("Write-off account is required for loan write-off.")
    
    # Dr Bad Debt Expense (Expense increases)
    gl_entry = frappe.get_doc({
        "doctype": "GL Entry",
        "posting_date": posting_date,
        "account": loan_doc.write_off_account,
        "debit": flt(writeoff_amount, 2),
        "credit": 0,
        "against": loan_doc.member,
        "party_type": "SHG Member",
        "party": loan_doc.member,
        "voucher_type": "SHG Loan Write-off",
        "voucher_no": f"LWO-{loan_doc.name}-{posting_date}",
        "company": company,
        "remarks": f"Loan write-off for {loan_doc.name}"
    })
    gl_entry.insert(ignore_permissions=True)
    gl_entry.submit()
    gl_entries.append(gl_entry.name)
    
    # Cr Loans Receivable (Asset decreases)
    gl_entry = frappe.get_doc({
        "doctype": "GL Entry",
        "posting_date": posting_date,
        "account": loan_doc.receivable_account,
        "debit": 0,
        "credit": flt(writeoff_amount, 2),
        "against": loan_doc.member,
        "party_type": "SHG Member",
        "party": loan_doc.member,
        "voucher_type": "SHG Loan Write-off",
        "voucher_no": f"LWO-{loan_doc.name}-{posting_date}",
        "company": company,
        "remarks": f"Loan write-off for {loan_doc.name}"
    })
    gl_entry.insert(ignore_permissions=True)
    gl_entry.submit()
    gl_entries.append(gl_entry.name)
    
    return gl_entries


def reverse_gl_entries(
    gl_entry_names: List[str],
    posting_date: str,
    company: str
) -> List[str]:
    """
    Reverse GL entries by creating contra entries.
    
    Args:
        gl_entry_names: List of GL entry names to reverse
        posting_date: Date of reversal
        company: Company name
        
    Returns:
        List of created reversal GL entry names
    """
    reversal_entries = []
    
    for gl_entry_name in gl_entry_names:
        original_entry = frappe.get_doc("GL Entry", gl_entry_name)
        
        # Create contra entry
        reversal_entry = frappe.get_doc({
            "doctype": "GL Entry",
            "posting_date": posting_date,
            "account": original_entry.account,
            "debit": original_entry.credit,  # Swap debit and credit
            "credit": original_entry.debit,   # Swap debit and credit
            "against": original_entry.against,
            "party_type": original_entry.party_type,
            "party": original_entry.party,
            "voucher_type": f"Reversal of {original_entry.voucher_type}",
            "voucher_no": f"REV-{original_entry.voucher_no}",
            "company": company,
            "remarks": f"Reversal of {original_entry.remarks}"
        })
        reversal_entry.insert(ignore_permissions=True)
        reversal_entry.submit()
        reversal_entries.append(reversal_entry.name)
    
    return reversal_entries


@frappe.whitelist()
def post_loan_disbursement(
    loan_name: str,
    posting_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Post loan disbursement to GL.
    
    Args:
        loan_name: Name of the SHG Loan document
        posting_date: Date of disbursement (default: today)
        
    Returns:
        Dictionary with posting results
    """
    if not posting_date:
        posting_date = frappe.utils.today()
    
    # Get loan document
    loan_doc = frappe.get_doc("SHG Loan", loan_name)
    
    # Validate loan status
    if loan_doc.status != "Approved":
        frappe.throw("Loan must be approved before disbursement.")
    
    # Create GL entries
    company = loan_doc.company or frappe.db.get_single_value("SHG Settings", "company")
    gl_entries = create_disbursement_gl_entries(loan_doc, posting_date, company)
    
    # Update loan document
    loan_doc.disbursement_date = posting_date
    loan_doc.status = "Disbursed"
    loan_doc.posted_to_gl = 1
    loan_doc.posted_on = frappe.utils.now_datetime()
    loan_doc.disbursement_journal_entry = gl_entries[0] if gl_entries else None
    loan_doc.save(ignore_permissions=True)
    
    return {
        "status": "success",
        "message": f"Loan disbursement posted successfully with {len(gl_entries)} GL entries.",
        "gl_entries": gl_entries
    }