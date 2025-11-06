import frappe
from frappe import _
from frappe.utils import flt, getdate, today
from shg.shg.loan_utils import update_loan_summary

@frappe.whitelist()
def pull_unpaid_installments(loan_name):
    """
    Fetch unpaid installments from repayment schedule for inline payment.
    
    Args:
        loan_name (str): Name of the SHG Loan document
        
    Returns:
        list: List of unpaid installments
    """
    try:
        # Get unpaid or partially paid installments
        installments = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={
                "parent": loan_name,
                "parenttype": "SHG Loan",
                "status": ["in", ["Pending", "Partially Paid", "Overdue"]]
            },
            fields=[
                "name",
                "installment_no",
                "due_date",
                "principal_component",
                "interest_component",
                "total_payment",
                "amount_paid",
                "unpaid_balance",
                "status"
            ],
            order_by="due_date asc"
        )
        
        # Add computed fields for inline payment
        for installment in installments:
            # remaining_amount is the same as unpaid_balance for display purposes
            installment["remaining_amount"] = flt(installment.get("unpaid_balance", 0), 2)
            # Default amount_to_pay to 0
            installment["amount_to_pay"] = 0
            # Default pay_now to False
            installment["pay_now"] = 0
            
        return installments
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to pull unpaid installments for {loan_name}")
        frappe.throw(_("Failed to fetch unpaid installments: {0}").format(str(e)))

@frappe.whitelist()
def post_inline_repayments(loan_name, repayments):
    """
    Process inline repayments and update schedule rows.
    
    Args:
        loan_name (str): Name of the SHG Loan document
        repayments (list): List of repayment data
        
    Returns:
        dict: Status and message
    """
    try:
        if not repayments:
            frappe.throw(_("No repayments to process"))
            
        total_paid = 0
        
        # Process each repayment
        for repayment in repayments:
            schedule_row_id = repayment.get("schedule_row_id")
            amount_to_pay = flt(repayment.get("amount_to_pay"))
            
            if amount_to_pay <= 0:
                continue
                
            # Get the schedule row
            schedule_row = frappe.get_doc("SHG Loan Repayment Schedule", schedule_row_id)
            
            # Validate amount doesn't exceed unpaid balance
            unpaid_balance = flt(schedule_row.unpaid_balance)
            if amount_to_pay > unpaid_balance:
                frappe.throw(_("Amount to pay ({0}) exceeds unpaid balance ({1}) for installment {2}").format(
                    amount_to_pay, unpaid_balance, schedule_row.installment_no))
            
            # Update the schedule row
            schedule_row.amount_paid = flt(schedule_row.amount_paid) + amount_to_pay
            schedule_row.unpaid_balance = flt(schedule_row.total_payment) - flt(schedule_row.amount_paid)
            
            # Update status
            if schedule_row.unpaid_balance <= 0:
                schedule_row.status = "Paid"
                schedule_row.actual_payment_date = today()
            elif flt(schedule_row.amount_paid) > 0:
                schedule_row.status = "Partially Paid"
            else:
                schedule_row.status = "Pending"
            
            # Save the updated row
            schedule_row.flags.ignore_validate_update_after_submit = True
            schedule_row.save(ignore_permissions=True)
            
            total_paid += amount_to_pay
        
        # Update loan summary
        update_loan_summary(loan_name)
        
        return {
            "status": "success",
            "message": _("Successfully processed repayments of {0}").format(total_paid),
            "total_paid": flt(total_paid, 2)
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to post inline repayments for {loan_name}")
        frappe.throw(_("Failed to process repayments: {0}").format(str(e)))

def validate_repayment_amount(loan_name, amount):
    """
    Validate that repayment amount doesn't exceed loan balance.
    
    Args:
        loan_name (str): Name of the SHG Loan document
        amount (float): Amount to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        # Get loan document
        loan_doc = frappe.get_doc("SHG Loan", loan_name)
        
        # Check if amount exceeds outstanding balance
        if flt(amount) > flt(loan_doc.outstanding_balance):
            return False
            
        return True
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to validate repayment amount for {loan_name}")
        return False

def calculate_remaining_balance(schedule_row):
    """
    Calculate remaining balance for an installment.
    
    Args:
        schedule_row (object): SHG Loan Repayment Schedule row
        
    Returns:
        float: Remaining balance
    """
    return flt(schedule_row.total_payment) - flt(schedule_row.amount_paid)