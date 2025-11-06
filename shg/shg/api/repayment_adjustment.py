import frappe
from frappe import _
from frappe.utils import flt, getdate

@frappe.whitelist()
def recalculate_installment_balances(loan_repayment_name):
    """
    Recalculate installment balances and remaining amounts for a loan repayment.
    
    Args:
        loan_repayment_name (str): Name of the SHG Loan Repayment document
        
    Returns:
        dict: Status and message
    """
    try:
        # Get the loan repayment document
        repayment_doc = frappe.get_doc("SHG Loan Repayment", loan_repayment_name)
        
        # Recalculate remaining balances for each installment
        total_amount = 0
        for row in repayment_doc.installment_adjustment:
            # Auto-calculate remaining balance
            row.remaining = flt(row.total_due) - flt(row.amount_to_repay)
            total_amount += flt(row.amount_to_repay)
        
        # Update total paid if it doesn't match
        if flt(total_amount) != flt(repayment_doc.total_paid):
            repayment_doc.total_paid = total_amount
            # Recalculate repayment breakdown
            repayment_doc.calculate_repayment_breakdown()
        
        # Save the document
        repayment_doc.save(ignore_permissions=True)
        
        return {
            "status": "success",
            "message": _("Installment balances recalculated successfully"),
            "total_paid": total_amount
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to recalculate installment balances")
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def refresh_installment_adjustment(loan_repayment_name):
    """
    Refresh installment adjustment table with current unpaid installments.
    
    Args:
        loan_repayment_name (str): Name of the SHG Loan Repayment document
        
    Returns:
        dict: Status and message
    """
    try:
        # Get the loan repayment document
        repayment_doc = frappe.get_doc("SHG Loan Repayment", loan_repayment_name)
        
        # Pull unpaid installments
        repayment_doc.pull_unpaid_installments()
        
        # Save the document
        repayment_doc.save(ignore_permissions=True)
        
        return {
            "status": "success",
            "message": _("Installment adjustment table refreshed successfully"),
            "installment_count": len(repayment_doc.installment_adjustment)
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to refresh installment adjustment")
        return {
            "status": "error",
            "message": str(e)
        }