import frappe
from frappe import _
from frappe.utils import flt, getdate, today
from shg.shg.loan.schedule import get_schedule, compute_totals

class ScheduleManager:
    """Manages loan repayment schedule operations."""
    
    def __init__(self, loan_name):
        self.loan_name = loan_name
        self.loan_doc = frappe.get_doc("SHG Loan", loan_name)
    
    def update_schedule_row_status(self, row_name, amount_paid=None):
        """
        Update a schedule row status based on payment amount.
        
        Args:
            row_name (str): Name of the schedule row
            amount_paid (float): Amount paid (optional, if provided will update amount)
        """
        row = frappe.get_doc("SHG Loan Repayment Schedule", row_name)
        
        if amount_paid is not None:
            # Update amount paid
            row.amount_paid = flt(amount_paid)
        
        # Calculate unpaid balance
        row.unpaid_balance = flt(row.total_payment) - flt(row.amount_paid)
        
        # Update status
        if row.unpaid_balance <= 0:
            row.status = "Paid"
        elif flt(row.amount_paid) > 0:
            row.status = "Partially Paid"
        else:
            row.status = "Pending"
        
        # Check if overdue
        if row.due_date and getdate(row.due_date) < getdate(today()) and row.unpaid_balance > 0:
            row.status = "Overdue"
        
        row.save(ignore_permissions=True)
        return row
    
    def mark_as_paid(self, row_name, amount=None):
        """
        Mark an installment as paid.
        
        Args:
            row_name (str): Name of the schedule row
            amount (float): Amount to mark as paid (optional, defaults to total payment)
        """
        row = frappe.get_doc("SHG Loan Repayment Schedule", row_name)
        amount_to_pay = flt(amount or row.total_payment)
        
        row.amount_paid = amount_to_pay
        row.unpaid_balance = max(0, flt(row.total_payment) - amount_to_pay)
        row.status = "Paid" if row.unpaid_balance == 0 else "Partially Paid"
        row.actual_payment_date = today()
        row.save()
        
        # Refresh loan summary
        self.refresh_loan_summary()
        
        frappe.msgprint(_("✅ Installment {0} marked as Paid ({1})").format(row_name, amount_to_pay))
        return row
    
    def refresh_loan_summary(self):
        """Refresh loan summary fields."""
        from shg.shg.loan_utils import update_loan_summary
        update_loan_summary(self.loan_name)
    
    def get_overdue_amount(self):
        """Calculate total overdue amount."""
        schedule = get_schedule(self.loan_name)
        overdue_amount = 0
        today_date = getdate(today())
        
        for r in schedule:
            if (r.get("status") not in ("Paid",) and 
                getdate(r.get("due_date")) < today_date and 
                flt(r.get("unpaid_balance", 0) or (
                    flt(r.get("total_payment", 0)) - flt(r.get("amount_paid", 0) or 0)
                )) > 0):
                overdue_amount += flt(r.get("unpaid_balance", 0) or (
                    flt(r.get("total_payment", 0)) - flt(r.get("amount_paid", 0) or 0)
                ))
        
        return overdue_amount
    
    def get_next_due_date(self):
        """Get the next due date from unpaid installments."""
        schedule = get_schedule(self.loan_name)
        next_due_date = None
        
        for r in sorted(schedule, key=lambda x: getdate(x.get("due_date", ""))):
            if r.get("status") not in ("Paid",) and flt(r.get("unpaid_balance", 0) or 0) > 0:
                next_due_date = r.get("due_date")
                break
        
        return next_due_date
    
    def recompute_all_schedule_rows(self):
        """
        Recompute all schedule rows from scratch.
        This is useful for data integrity maintenance.
        """
        # Reset all rows
        rows = frappe.get_all(
            "SHG Loan Repayment Schedule", 
            filters={"parent": self.loan_name}, 
            fields=["name", "total_payment"]
        )
        
        for r in rows:
            frappe.db.set_value("SHG Loan Repayment Schedule", r.name, {
                "amount_paid": 0, 
                "unpaid_balance": r.get("total_payment", 0), 
                "status": "Pending"
            }, update_modified=False)
        
        # Read repayments in posting_date order
        pays = frappe.get_all(
            "SHG Loan Repayment", 
            filters={"loan": self.loan_name, "docstatus": 1}, 
            fields=["total_paid"], 
            order_by="posting_date asc, creation asc"
        )
        
        from shg.shg.loan_utils import allocate_payment_to_schedule
        for p in pays:
            allocate_payment_to_schedule(self.loan_name, p.get("total_paid", 0))
        
        # Refresh loan summary
        self.refresh_loan_summary()

@frappe.whitelist()
def update_schedule_row(loan_name, row_name, amount_paid):
    """API endpoint to update a schedule row."""
    manager = ScheduleManager(loan_name)
    row = manager.update_schedule_row_status(row_name, amount_paid)
    return {
        "status": "success",
        "message": _("Schedule row updated successfully"),
        "row": row.as_dict()
    }

@frappe.whitelist()
def mark_installment_paid(loan_name, row_name, amount=None):
    """API endpoint to mark an installment as paid."""
    manager = ScheduleManager(loan_name)
    row = manager.mark_as_paid(row_name, amount)
    return {
        "status": "success",
        "message": _("Installment marked as paid successfully"),
        "row": row.as_dict()
    }

@frappe.whitelist()
def refresh_schedule_summary(loan_name):
    """API endpoint to refresh schedule summary."""
    manager = ScheduleManager(loan_name)
    manager.refresh_loan_summary()
    return {
        "status": "success",
        "message": _("Loan summary refreshed successfully")
    }

@frappe.whitelist()
def recompute_schedule(loan_name):
    """API endpoint to recompute entire schedule."""
    manager = ScheduleManager(loan_name)
    manager.recompute_all_schedule_rows()
    return {
        "status": "success",
        "message": _("Schedule recomputed successfully")
    }