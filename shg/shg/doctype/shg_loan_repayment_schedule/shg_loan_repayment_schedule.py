import frappe
from frappe.model.document import Document
from frappe.utils import getdate, flt

class SHGLoanRepaymentSchedule(Document):
    def validate(self):
        # Set total_due as sum of principal and interest
        self.total_due = flt(self.principal_amount) + flt(self.interest_amount)
        
        # Calculate unpaid_balance
        self.unpaid_balance = flt(self.total_due) - flt(self.amount_paid or 0)
        
        # Set status based on payment and due date
        self.set_status()
        
    def set_status(self):
        """Set status based on payment and due date"""
        today = getdate()
        due_date = getdate(self.due_date) if self.due_date else today
        
        if self.amount_paid and flt(self.amount_paid) >= flt(self.total_due):
            self.status = "Paid"
        elif self.amount_paid and flt(self.amount_paid) > 0:
            self.status = "Partially Paid"
        elif due_date < today:
            self.status = "Overdue"
        else:
            self.status = "Pending"