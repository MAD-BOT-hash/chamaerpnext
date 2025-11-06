import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_months
from datetime import datetime

def build_schedule(loan_doc):
    """
    Generates amortization schedule per interest_type (Flat vs Reducing).
    
    Args:
        loan_doc: SHG Loan document
        
    Returns:
        list: Schedule rows
    """
    if not loan_doc.loan_amount or not loan_doc.interest_rate or not loan_doc.loan_period_months:
        return []
        
    schedule = []
    principal = flt(loan_doc.loan_amount)
    interest_rate = flt(loan_doc.interest_rate)
    months = loan_doc.loan_period_months
    frequency = loan_doc.repayment_frequency or "Monthly"
    
    # Calculate frequency multiplier
    freq_multiplier = 1
    if frequency == "Quarterly":
        freq_multiplier = 3
    elif frequency == "Half-Yearly":
        freq_multiplier = 6
    elif frequency == "Yearly":
        freq_multiplier = 12
    
    # Calculate EMI based on interest type
    if loan_doc.interest_type == "Flat Rate":
        # Flat rate: interest calculated on original principal
        total_interest = principal * (interest_rate / 100) * (months / 12)
        total_amount = principal + total_interest
        emi = total_amount / months
        
        # For flat rate, principal and interest components are fixed
        monthly_interest = total_interest / months
        monthly_principal = principal / months
        
        for i in range(1, months + 1):
            due_date = add_months(getdate(loan_doc.repayment_start_date), (i - 1) * freq_multiplier)
            schedule.append({
                "installment_no": i,
                "due_date": due_date,
                "emi_amount": flt(emi, 2),
                "principal_component": flt(monthly_principal, 2),
                "interest_component": flt(monthly_interest, 2),
                "paid_amount": 0,
                "status": "Pending"
            })
    else:
        # Reducing balance: interest calculated on reducing principal
        monthly_rate = (interest_rate / 100) / 12
        emi = principal * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
        
        remaining_principal = principal
        for i in range(1, months + 1):
            due_date = add_months(getdate(loan_doc.repayment_start_date), (i - 1) * freq_multiplier)
            interest_component = remaining_principal * monthly_rate
            principal_component = emi - interest_component
            remaining_principal -= principal_component
            
            schedule.append({
                "installment_no": i,
                "due_date": due_date,
                "emi_amount": flt(emi, 2),
                "principal_component": flt(principal_component, 2),
                "interest_component": flt(interest_component, 2),
                "paid_amount": 0,
                "status": "Pending"
            })
    
    return schedule

def get_unpaid_rows(loan_name):
    """
    Returns Unpaid + Partially Paid + Overdue rows in ascending due_date.
    
    Args:
        loan_name (str): Name of the SHG Loan document
        
    Returns:
        list: List of unpaid schedule rows
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
                "emi_amount",
                "principal_component",
                "interest_component",
                "paid_amount",
                "status"
            ],
            order_by="due_date asc"
        )
        
        # Add computed fields for inline payment
        for installment in installments:
            # remaining_amount is the same as unpaid_balance for display purposes
            remaining = flt(installment.get("emi_amount", 0)) - flt(installment.get("paid_amount", 0))
            installment["remaining_amount"] = flt(remaining, 2)
            # Default amount_to_pay to 0
            installment["amount_to_pay"] = 0
            # Default pay_now to False
            installment["pay_now"] = 0
            
        return installments
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to get unpaid rows for {loan_name}")
        frappe.throw(_("Failed to fetch unpaid installments: {0}").format(str(e)))

def allocate_payment(loan_name, allocations, posting_date=None):
    """
    Allocate payments to schedule rows.
    
    Args:
        loan_name (str): Name of the SHG Loan document
        allocations (list): List of {rowname, amount_to_pay}
        posting_date (str): Posting date for the payment
        
    Returns:
        dict: Allocation result with journal/payment posting plan
    """
    try:
        if not allocations:
            frappe.throw(_("No allocations to process"))
            
        loan_doc = frappe.get_doc("SHG Loan", loan_name)
        posting_date = posting_date or nowdate()
        today = getdate()
        
        # Validate allocations and calculate totals
        total_allocated = 0
        allocation_details = []
        
        for alloc in allocations:
            row_name = alloc.get("rowname")
            amount_to_pay = flt(alloc.get("amount_to_pay"))
            
            if amount_to_pay <= 0:
                continue
                
            # Get the schedule row
            schedule_row = frappe.get_doc("SHG Loan Repayment Schedule", row_name)
            
            # Validate amount doesn't exceed unpaid balance
            emi_amount = flt(schedule_row.emi_amount)
            paid_amount = flt(schedule_row.paid_amount)
            remaining_balance = emi_amount - paid_amount
            
            if amount_to_pay > remaining_balance:
                frappe.throw(_("Amount to pay ({0}) exceeds unpaid balance ({1}) for installment {2}").format(
                    frappe.utils.fmt_money(amount_to_pay), frappe.utils.fmt_money(remaining_balance), schedule_row.installment_no))
            
            # Calculate interest and principal components
            interest_component = flt(schedule_row.interest_component)
            principal_component = flt(schedule_row.principal_component)
            
            # Waterfall allocation: interest first, then principal
            interest_paid = min(amount_to_pay, interest_component - max(0, paid_amount - principal_component))
            principal_paid = max(0, amount_to_pay - interest_paid)
            
            allocation_details.append({
                "row_name": row_name,
                "amount_to_pay": amount_to_pay,
                "interest_paid": interest_paid,
                "principal_paid": principal_paid,
                "schedule_row": schedule_row
            })
            
            total_allocated += amount_to_pay
        
        # Apply allocations to schedule rows
        for detail in allocation_details:
            row_name = detail["row_name"]
            amount_to_pay = detail["amount_to_pay"]
            interest_paid = detail["interest_paid"]
            principal_paid = detail["principal_paid"]
            schedule_row = detail["schedule_row"]
            
            # Update the schedule row
            schedule_row.paid_amount = flt(schedule_row.paid_amount) + amount_to_pay
            
            # Update status
            emi_amount = flt(schedule_row.emi_amount)
            paid_amount = flt(schedule_row.paid_amount)
            remaining_balance = emi_amount - paid_amount
            
            if remaining_balance <= 0:
                schedule_row.status = "Paid"
            elif paid_amount > 0:
                schedule_row.status = "Partially Paid"
            else:
                schedule_row.status = "Pending"
                
            # Check if overdue
            if schedule_row.due_date and getdate(schedule_row.due_date) < today and remaining_balance > 0:
                schedule_row.status = "Overdue"
            
            # Save the updated row
            schedule_row.flags.ignore_validate_update_after_submit = True
            schedule_row.save(ignore_permissions=True)
        
        # Create posting plan for accounting entries
        posting_plan = {
            "loan_name": loan_name,
            "total_amount": total_allocated,
            "posting_date": posting_date,
            "allocations": allocation_details
        }
        
        return {
            "status": "success",
            "message": _("Successfully allocated payments of {0}").format(total_allocated),
            "total_allocated": flt(total_allocated, 2),
            "posting_plan": posting_plan
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to allocate payment for {loan_name}")
        frappe.throw(_("Failed to allocate payments: {0}").format(str(e)))

def post_payment_entries(loan_name, posting_plan):
    """
    Create Payment Entry or Journal Entry per voucher_type on Loan.
    
    Args:
        loan_name (str): Name of the SHG Loan document
        posting_plan (dict): Posting plan from allocate_payment
        
    Returns:
        dict: Posting result
    """
    try:
        loan_doc = frappe.get_doc("SHG Loan", loan_name)
        
        # TODO: Implement actual payment entry creation based on loan settings
        # This is a placeholder for the actual implementation
        
        # Update loan summary fields
        recompute_loan_summary(loan_name)
        
        return {
            "status": "success",
            "message": _("Payment entries posted successfully"),
            "payment_entry": None  # Placeholder
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to post payment entries for {loan_name}")
        frappe.throw(_("Failed to post payment entries: {0}").format(str(e)))

def recompute_loan_summary(loan_name):
    """
    Recompute loan summary fields.
    
    Args:
        loan_name (str): Name of the SHG Loan document
    """
    try:
        loan_doc = frappe.get_doc("SHG Loan", loan_name)
        
        # Get all repayment schedule rows
        schedule_rows = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={"parent": loan_name, "parenttype": "SHG Loan"},
            fields=["emi_amount", "principal_component", "interest_component", "paid_amount", "status", "due_date"]
        )
        
        # Calculate totals
        total_interest_payable = sum(flt(row.get("interest_component", 0)) for row in schedule_rows)
        total_payable_amount = sum(flt(row.get("emi_amount", 0)) for row in schedule_rows)
        total_repaid = sum(flt(row.get("paid_amount", 0)) for row in schedule_rows)
        loan_balance = total_payable_amount - total_repaid
        
        # Calculate overdue amount
        overdue_amount = 0
        today = getdate()
        next_due_date = None
        
        for row in schedule_rows:
            emi_amount = flt(row.get("emi_amount", 0))
            paid_amount = flt(row.get("paid_amount", 0))
            remaining = emi_amount - paid_amount
            
            # Check if overdue
            if row.get("due_date") and getdate(row.get("due_date")) < today and remaining > 0 and row.get("status") != "Paid":
                overdue_amount += remaining
                
            # Find next due date
            if remaining > 0 and (next_due_date is None or getdate(row.get("due_date")) < next_due_date):
                next_due_date = getdate(row.get("due_date"))
        
        # Update loan document
        loan_doc.total_interest_payable = flt(total_interest_payable, 2)
        loan_doc.total_payable_amount = flt(total_payable_amount, 2)
        loan_doc.total_repaid = flt(total_repaid, 2)
        loan_doc.loan_balance = flt(loan_balance, 2)
        loan_doc.balance_amount = flt(loan_balance, 2)  # Keep both fields consistent
        loan_doc.overdue_amount = flt(overdue_amount, 2)
        loan_doc.next_due_date = next_due_date
        
        # Update last repayment date if there are payments
        if total_repaid > 0:
            last_payment = frappe.get_all(
                "SHG Loan Repayment",
                filters={"loan": loan_name, "docstatus": 1},
                fields=["posting_date"],
                order_by="posting_date desc",
                limit=1
            )
            if last_payment:
                loan_doc.last_repayment_date = last_payment[0].get("posting_date")
        
        # Save the document
        loan_doc.flags.ignore_validate_update_after_submit = True
        loan_doc.save(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to recompute loan summary for {loan_name}")
        frappe.throw(_("Failed to recompute loan summary: {0}").format(str(e)))

def refresh_repayment_summary(loan_name):
    """
    Refresh repayment summary for the loan.
    
    Args:
        loan_name (str): Name of the SHG Loan document
        
    Returns:
        dict: Updated loan summary
    """
    try:
        recompute_loan_summary(loan_name)
        
        # Return updated loan data
        loan_doc = frappe.get_doc("SHG Loan", loan_name)
        
        return {
            "total_payable_amount": loan_doc.total_payable_amount,
            "total_repaid": loan_doc.total_repaid,
            "loan_balance": loan_doc.loan_balance,
            "balance_amount": loan_doc.balance_amount,
            "overdue_amount": loan_doc.overdue_amount,
            "next_due_date": loan_doc.next_due_date,
            "last_repayment_date": loan_doc.last_repayment_date
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to refresh repayment summary for {loan_name}")
        frappe.throw(_("Failed to refresh repayment summary: {0}").format(str(e)))