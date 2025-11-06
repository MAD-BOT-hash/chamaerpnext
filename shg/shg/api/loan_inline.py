import frappe
from frappe import _
from frappe.utils import flt, getdate, today
from shg.shg.loan_utils import update_loan_summary

@frappe.whitelist()
def pull_unpaid_installments(loan_name):
    """
    Populate schedule grid with unpaid/partly paid rows, compute remaining_amount.
    
    Args:
        loan_name (str): Name of the SHG Loan document
        
    Returns:
        list: List of unpaid installments with computed fields
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
        
        # Compute remaining_amount for each installment
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
def compute_inline_totals(loan_name):
    """
    Compute selected_to_pay, overdue, outstanding dynamically.
    
    Args:
        loan_name (str): Name of the SHG Loan document
        
    Returns:
        dict: Computed totals
    """
    try:
        # Get all installments
        installments = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={
                "parent": loan_name,
                "parenttype": "SHG Loan"
            },
            fields=[
                "total_payment",
                "amount_paid",
                "unpaid_balance",
                "status",
                "due_date"
            ]
        )
        
        # Calculate totals
        total_selected = 0
        overdue_amount = 0
        outstanding_amount = 0
        today_date = getdate(today())
        
        for installment in installments:
            # Add to outstanding amount
            outstanding_amount += flt(installment.get("unpaid_balance", 0))
            
            # Check if overdue
            due_date = getdate(installment.get("due_date"))
            if (installment.get("status") != "Paid" and 
                due_date < today_date and 
                flt(installment.get("unpaid_balance", 0)) > 0):
                overdue_amount += flt(installment.get("unpaid_balance", 0))
        
        return {
            "total_selected": flt(total_selected, 2),
            "overdue_amount": flt(overdue_amount, 2),
            "outstanding_amount": flt(outstanding_amount, 2)
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to compute inline totals for {loan_name}")
        frappe.throw(_("Failed to compute totals: {0}").format(str(e)))

@frappe.whitelist()
def post_inline_repayments(loan_name, repayments):
    """
    Validate and apply input amounts, update paid_amount, status, and loan totals.
    
    Args:
        loan_name (str): Name of the SHG Loan document
        repayments (list): List of repayment data with schedule_row_id, amount_to_pay
        
    Returns:
        dict: Status and message
    """
    try:
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
            
            # Save the updated row
            schedule_row.flags.ignore_validate_update_after_submit = True
            schedule_row.save(ignore_permissions=True)
            
            total_paid += amount_to_pay
        
        # Update loan summary
        update_loan_summary(loan_name)
        
        # Reload the loan document
        loan_doc = frappe.get_doc("SHG Loan", loan_name)
        loan_doc.reload()
        
        return {
            "status": "success",
            "message": _("Successfully processed repayments of {0}").format(total_paid),
            "total_paid": flt(total_paid, 2)
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to post inline repayments for {loan_name}")
        frappe.throw(_("Failed to process repayments: {0}").format(str(e)))

def get_installment_remaining_balance(schedule_row):
    """
    Calculate installment remaining balance.
    
    Args:
        schedule_row (object): SHG Loan Repayment Schedule row
        
    Returns:
        float: Remaining balance
    """
    return flt(schedule_row.total_payment) - flt(schedule_row.amount_paid)

def compute_aggregate_totals(loan_name):
    """
    Compute aggregate totals (outstanding = principal + interest unpaid).
    
    Args:
        loan_name (str): Name of the SHG Loan document
        
    Returns:
        dict: Aggregate totals
    """
    try:
        installments = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={
                "parent": loan_name,
                "parenttype": "SHG Loan"
            },
            fields=[
                "principal_component",
                "interest_component",
                "amount_paid",
                "unpaid_balance"
            ]
        )
        
        total_principal_unpaid = 0
        total_interest_unpaid = 0
        total_outstanding = 0
        
        for installment in installments:
            total_principal_unpaid += flt(installment.get("principal_component", 0))
            total_interest_unpaid += flt(installment.get("interest_component", 0))
            total_outstanding += flt(installment.get("unpaid_balance", 0))
            
        return {
            "total_principal_unpaid": flt(total_principal_unpaid, 2),
            "total_interest_unpaid": flt(total_interest_unpaid, 2),
            "total_outstanding": flt(total_outstanding, 2)
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to compute aggregate totals for {loan_name}")
        return {
            "total_principal_unpaid": 0,
            "total_interest_unpaid": 0,
            "total_outstanding": 0
        }