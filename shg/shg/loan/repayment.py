import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_days
from shg.shg.utils.account_helpers import get_or_create_member_receivable
from shg.shg.loan.schedule import get_schedule, compute_totals
from shg.shg.loan.accounting import create_payment_entry

class SHGLoanRepaymentService:
    """Central service for handling SHG Loan Repayment operations."""
    
    def __init__(self, loan_name):
        self.loan_name = loan_name
        self.loan_doc = frappe.get_doc("SHG Loan", loan_name)
    
    def validate_repayment(self, repayment_amount):
        """Validate repayment amount against loan balance."""
        if flt(repayment_amount) <= 0:
            frappe.throw(_("Repayment amount must be greater than 0."))
        
        # Get current loan balance
        schedule = get_schedule(self.loan_name)
        totals = compute_totals(schedule)
        outstanding_total = totals["outstanding_balance"]
        
        if flt(repayment_amount) > flt(outstanding_total):
            frappe.throw(
                _("Repayment ({0}) exceeds remaining balance ({1}).").format(
                    repayment_amount, outstanding_total
                )
            )
    
    def fetch_unpaid_installments(self):
        """Fetch unpaid installments from the linked loan's repayment schedule."""
        schedule = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={
                "parent": self.loan_name, 
                "status": ("in", ["Unpaid", "Partially Paid", "Pending", "Overdue"])
            },
            fields=[
                "name", "installment_no", "due_date", "emi_amount", 
                "principal_component", "interest_component", "total_payment", 
                "amount_paid", "unpaid_balance", "status"
            ]
        )
        
        return schedule
    
    def allocate_payment(self, payment_amount, installment_allocations=None):
        """
        Allocate payment to loan schedule.
        
        Args:
            payment_amount (float): Total payment amount
            installment_allocations (list): Optional list of {row_name, amount_to_pay} for specific allocations
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
            return self._allocate_to_specific_installments(installment_allocations, schedule)
        else:
            # Otherwise, allocate to earliest unpaid installments
            return self._allocate_to_earliest_installments(to_allocate, schedule)
    
    def _allocate_to_specific_installments(self, allocations, schedule):
        """Allocate payment to specific installments."""
        total_allocated = 0
        allocation_details = []
        
        for alloc in allocations:
            row_name = alloc.get("row_name")
            amount_to_pay = flt(alloc.get("amount_to_pay"))
            
            if amount_to_pay <= 0:
                continue
                
            # Get the schedule row
            schedule_row = None
            for r in schedule:
                if r.get("name") == row_name:
                    schedule_row = r
                    break
                    
            if not schedule_row:
                frappe.throw(_("Invalid schedule row: {0}").format(row_name))
            
            # Validate amount doesn't exceed unpaid balance
            unpaid_balance = flt(schedule_row.get("unpaid_balance", 0) or (
                flt(schedule_row.get("total_payment", 0)) - flt(schedule_row.get("amount_paid", 0) or 0)
            ))
            
            if amount_to_pay > unpaid_balance:
                frappe.throw(_("Amount to pay ({0}) exceeds unpaid balance ({1}) for installment {2}").format(
                    frappe.utils.fmt_money(amount_to_pay), 
                    frappe.utils.fmt_money(unpaid_balance), 
                    schedule_row.get("installment_no")
                ))
            
            # Update the schedule row
            new_paid = flt(schedule_row.get("amount_paid", 0) or 0) + amount_to_pay
            new_unpaid = flt(schedule_row.get("total_payment", 0)) - new_paid
            new_status = "Paid" if new_unpaid <= 0.00001 else "Partially Paid"
            
            frappe.db.set_value("SHG Loan Repayment Schedule", row_name, {
                "amount_paid": new_paid,
                "unpaid_balance": max(new_unpaid, 0),
                "status": new_status
            }, update_modified=False)
            
            allocation_details.append({
                "row_name": row_name,
                "amount_paid": amount_to_pay,
                "principal_paid": min(amount_to_pay, flt(schedule_row.get("principal_component", 0))),
                "interest_paid": max(0, amount_to_pay - flt(schedule_row.get("principal_component", 0)))
            })
            
            total_allocated += amount_to_pay
        
        # Update loan summary
        from shg.shg.loan_utils import update_loan_summary
        update_loan_summary(self.loan_name)
        
        return {
            "total_allocated": total_allocated,
            "allocation_details": allocation_details
        }
    
    def _allocate_to_earliest_installments(self, to_allocate, schedule):
        """Allocate payment to earliest unpaid installments."""
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
    
    def post_to_ledger(self, repayment_doc):
        """Post repayment to ledger by creating a Payment Entry."""
        try:
            # Get member details
            member = frappe.get_doc("SHG Member", self.loan_doc.member)
            customer = member.customer or self.loan_doc.member
            
            # Get or create member receivable account
            company = self.loan_doc.company or frappe.db.get_single_value("SHG Settings", "company")
            member_account = get_or_create_member_receivable(self.loan_doc.member, company)
            
            # Create Payment Entry
            pe = frappe.new_doc("Payment Entry")
            pe.payment_type = "Receive"
            pe.company = company
            pe.posting_date = repayment_doc.posting_date
            pe.paid_from = member_account
            pe.paid_from_account_type = "Receivable"
            pe.paid_from_account_currency = frappe.db.get_value("Account", member_account, "account_currency")
            pe.paid_to = frappe.db.get_single_value("SHG Settings", "default_bank_account") or "Cash - " + frappe.db.get_value("Company", company, "abbr")
            pe.paid_to_account_type = "Cash"
            pe.paid_to_account_currency = frappe.db.get_value("Account", pe.paid_to, "account_currency")
            pe.paid_amount = flt(repayment_doc.total_paid)
            pe.received_amount = flt(repayment_doc.total_paid)
            pe.allocate_payment_amount = 1
            pe.party_type = "Customer"
            pe.party = customer
            pe.remarks = f"Loan repayment for {self.loan_name}"
            
            # Add reference to the loan
            pe.append("references", {
                "reference_doctype": "SHG Loan",
                "reference_name": self.loan_name,
                "total_amount": flt(self.loan_doc.balance_amount),
                "outstanding_amount": flt(self.loan_doc.balance_amount),
                "allocated_amount": flt(repayment_doc.total_paid)
            })
            
            pe.insert(ignore_permissions=True)
            pe.submit()
            
            # Link payment entry to repayment
            repayment_doc.db_set("payment_entry", pe.name)
            
            return pe.name
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to post repayment to ledger for {repayment_doc.name}")
            frappe.throw(f"Failed to post repayment to ledger: {str(e)}")

@frappe.whitelist()
def get_unpaid_installments(loan_name):
    """API endpoint to fetch unpaid installments."""
    service = SHGLoanRepaymentService(loan_name)
    return service.fetch_unpaid_installments()

@frappe.whitelist()
def validate_repayment_amount(loan_name, repayment_amount):
    """API endpoint to validate repayment amount."""
    service = SHGLoanRepaymentService(loan_name)
    service.validate_repayment(repayment_amount)
    return {"status": "valid"}

@frappe.whitelist()
def allocate_loan_payment(loan_name, payment_amount, installment_allocations=None):
    """API endpoint to allocate loan payment."""
    service = SHGLoanRepaymentService(loan_name)
    return service.allocate_payment(payment_amount, installment_allocations)

@frappe.whitelist()
def post_repayment_to_ledger(loan_name, repayment_name):
    """API endpoint to post repayment to ledger."""
    service = SHGLoanRepaymentService(loan_name)
    repayment_doc = frappe.get_doc("SHG Loan Repayment", repayment_name)
    payment_entry = service.post_to_ledger(repayment_doc)
    return {"payment_entry": payment_entry}