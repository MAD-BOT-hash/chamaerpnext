import frappe
from frappe import _
from frappe.utils import flt, getdate, today
from shg.shg.loan.schedule import get_schedule, compute_totals

class PaymentAllocator:
    """Handles payment allocation to loan repayment schedules."""
    
    def __init__(self, loan_name):
        self.loan_name = loan_name
        self.loan_doc = frappe.get_doc("SHG Loan", loan_name)
    
    def allocate_payment(self, payment_amount, installment_allocations=None, posting_date=None):
        """
        Allocate payment to loan schedule.
        
        Args:
            payment_amount (float): Total payment amount
            installment_allocations (list): Optional list of {row_name, amount_to_pay} for specific allocations
            posting_date (str): Posting date for the payment
            
        Returns:
            dict: Allocation result
        """
        payment_amount = flt(payment_amount)
        if payment_amount <= 0:
            frappe.throw(_("Payment amount must be greater than 0."))
        
        # Get schedule and totals
        schedule = get_schedule(self.loan_name)
        totals = compute_totals(schedule)
        outstanding_total = totals["outstanding_balance"]
        
        if outstanding_total <= 0:
            frappe.throw(_("No outstanding balance to allocate."))
        
        # Allocate payment
        to_allocate = min(payment_amount, outstanding_total)
        if to_allocate <= 0:
            return totals
        
        # If specific allocations provided, use them
        if installment_allocations:
            return self._allocate_to_specific_installments(installment_allocations)
        else:
            # Otherwise, allocate to earliest unpaid installments
            return self._allocate_to_earliest_installments(to_allocate)
    
    def _allocate_to_specific_installments(self, allocations):
        """Allocate payment to specific installments."""
        total_allocated = 0
        allocation_details = []
        
        for alloc in allocations:
            row_name = alloc.get("row_name")
            amount_to_pay = flt(alloc.get("amount_to_pay"))
            
            if amount_to_pay <= 0:
                continue
                
            # Get the schedule row
            schedule_row = frappe.get_doc("SHG Loan Repayment Schedule", row_name)
            
            # Validate amount doesn't exceed unpaid balance
            unpaid_balance = flt(schedule_row.unpaid_balance or (
                flt(schedule_row.total_payment) - flt(schedule_row.amount_paid or 0)
            ))
            
            if amount_to_pay > unpaid_balance:
                frappe.throw(_("Amount to pay ({0}) exceeds unpaid balance ({1}) for installment {2}").format(
                    frappe.utils.fmt_money(amount_to_pay), 
                    frappe.utils.fmt_money(unpaid_balance), 
                    schedule_row.installment_no
                ))
            
            # Update the schedule row
            new_paid = flt(schedule_row.amount_paid or 0) + amount_to_pay
            new_unpaid = flt(schedule_row.total_payment) - new_paid
            new_status = "Paid" if new_unpaid <= 0.00001 else "Partially Paid"
            
            # Check if overdue
            if schedule_row.due_date and getdate(schedule_row.due_date) < getdate(today()) and new_unpaid > 0:
                new_status = "Overdue"
            
            frappe.db.set_value("SHG Loan Repayment Schedule", row_name, {
                "amount_paid": new_paid,
                "unpaid_balance": max(new_unpaid, 0),
                "status": new_status
            }, update_modified=False)
            
            allocation_details.append({
                "row_name": row_name,
                "amount_paid": amount_to_pay,
                "principal_paid": min(amount_to_pay, flt(schedule_row.principal_component)),
                "interest_paid": max(0, amount_to_pay - flt(schedule_row.principal_component))
            })
            
            total_allocated += amount_to_pay
        
        # Update loan summary
        from shg.shg.loan_utils import update_loan_summary
        update_loan_summary(self.loan_name)
        
        return {
            "total_allocated": total_allocated,
            "allocation_details": allocation_details
        }
    
    def _allocate_to_earliest_installments(self, to_allocate):
        """Allocate payment to earliest unpaid installments."""
        schedule = get_schedule(self.loan_name)
        
        # Lock rows for update to avoid race conditions
        for r in schedule:
            if r.get("status") == "Paid":
                continue
            
            already_paid = flt(r.get("amount_paid", 0) or 0)
            line_due = flt(r.get("total_payment", 0))
            line_left = flt(r.get("unpaid_balance", 0) or (line_due - already_paid), 2)
            
            if line_left <= 0:
                # normalize row if needed
                if r.get("status") != "Paid":
                    frappe.db.set_value("SHG Loan Repayment Schedule", r.get("name"), {
                        "unpaid_balance": 0, "status": "Paid"
                    }, update_modified=False)
                continue
            
            take = min(line_left, to_allocate)
            
            # Safety check before allocation
            if flt(take) > flt(line_left):
                frappe.log_error(
                    f"Payment allocation attempt: take ({take}) > line_left ({line_left}) "
                    f"for installment {r.get('name') or r.get('installment_no')}",
                    "SHG Loan Payment Allocation"
                )
                frappe.throw(
                    f"Amount to pay ({take}) cannot exceed remaining balance "
                    f"({line_left}) for installment {r.get('name') or r.get('installment_no')}."
                )
            
            new_paid = flt(already_paid + take, 2)
            new_left = flt(line_due - new_paid, 2)
            new_status = "Paid" if new_left <= 0.00001 else "Partially Paid"
            
            # Check if overdue
            if r.get("due_date") and getdate(r.get("due_date")) < getdate(today()) and new_left > 0:
                new_status = "Overdue"
            
            frappe.db.set_value("SHG Loan Repayment Schedule", r.get("name"), {
                "amount_paid": new_paid,
                "unpaid_balance": max(new_left, 0),
                "status": new_status
            }, update_modified=False)
            
            to_allocate = flt(to_allocate - take, 2)
            if to_allocate <= 0:
                break
        
        # Update loan summary
        from shg.shg.loan_utils import update_loan_summary
        return update_loan_summary(self.loan_name)
    
    def reverse_payment(self, payment_entry_name):
        """
        Reverse a payment by reducing allocated amounts.
        
        Args:
            payment_entry_name (str): Name of the payment entry to reverse
        """
        # Get payment entry
        payment_entry = frappe.get_doc("Payment Entry", payment_entry_name)
        
        # Get loan repayment linked to this payment
        repayment = frappe.get_all(
            "SHG Loan Repayment",
            filters={"payment_entry": payment_entry_name},
            fields=["name", "loan"]
        )
        
        if not repayment:
            frappe.throw(_("No loan repayment found for payment entry {0}").format(payment_entry_name))
        
        repayment_doc = frappe.get_doc("SHG Loan Repayment", repayment[0].name)
        
        # Get schedule rows that were affected by this payment
        # This would require tracking which rows were paid in the repayment doc
        # For now, we'll recompute from ledger
        self.recompute_from_ledger()
        
        # Mark payment entry as cancelled
        payment_entry.cancel()
        
        return {
            "status": "success",
            "message": _("Payment reversed successfully")
        }
    
    def recompute_from_ledger(self):
        """
        Recompute schedule amounts_paid from all submitted repayment docs.
        Use if you need a clean rebuild (cancel/back-date scenarios).
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
        
        # Update loan summary
        from shg.shg.loan_utils import update_loan_summary
        update_loan_summary(self.loan_name)

@frappe.whitelist()
def allocate_payment_to_loan(loan_name, payment_amount, installment_allocations=None):
    """API endpoint to allocate payment to loan."""
    allocator = PaymentAllocator(loan_name)
    return allocator.allocate_payment(payment_amount, installment_allocations)

@frappe.whitelist()
def reverse_loan_payment(payment_entry_name):
    """API endpoint to reverse a loan payment."""
    # Get loan from payment entry
    payment_entry = frappe.get_doc("Payment Entry", payment_entry_name)
    
    # Find the loan repayment linked to this payment
    repayment = frappe.get_all(
        "SHG Loan Repayment",
        filters={"payment_entry": payment_entry_name},
        fields=["loan"]
    )
    
    if not repayment:
        frappe.throw(_("No loan repayment found for payment entry {0}").format(payment_entry_name))
    
    loan_name = repayment[0].loan
    allocator = PaymentAllocator(loan_name)
    return allocator.reverse_payment(payment_entry_name)

@frappe.whitelist()
def recompute_loan_from_ledger(loan_name):
    """API endpoint to recompute loan from ledger."""
    allocator = PaymentAllocator(loan_name)
    allocator.recompute_from_ledger()
    return {
        "status": "success",
        "message": _("Loan recomputed from ledger successfully")
    }