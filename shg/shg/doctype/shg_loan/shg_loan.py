import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, getdate, add_months, flt
import math

class SHGLoan(Document):
    def validate(self):
        self.validate_amount()
        self.validate_interest_rate()
        self.calculate_repayment_details()
        
    def validate_amount(self):
        """Validate loan amount"""
        if self.loan_amount <= 0:
            frappe.throw(_("Loan amount must be greater than zero"))
            
    def validate_interest_rate(self):
        """Validate interest rate"""
        if self.interest_rate < 0:
            frappe.throw(_("Interest rate cannot be negative"))
            
    def calculate_repayment_details(self):
        """Calculate repayment details"""
        if self.loan_amount and self.interest_rate and self.loan_period_months:
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                total_interest = self.loan_amount * (self.interest_rate / 100) * (self.loan_period_months / 12)
                self.total_payable = self.loan_amount + total_interest
                self.monthly_installment = self.total_payable / self.loan_period_months
            else:
                # Reducing balance calculation
                monthly_rate = (self.interest_rate / 100) / 12
                if monthly_rate > 0:
                    self.monthly_installment = (self.loan_amount * monthly_rate * 
                                             (1 + monthly_rate) ** self.loan_period_months) / \
                                             ((1 + monthly_rate) ** self.loan_period_months - 1)
                else:
                    self.monthly_installment = self.loan_amount / self.loan_period_months
                    
                # For display purposes, calculate total payable
                self.total_payable = self.monthly_installment * self.loan_period_months
                
    def on_submit(self):
        if self.status == "Approved":
            self.generate_repayment_schedule()
            self.update_member_summary()
            self.send_approval_notification()
            
    def on_update(self):
        """Update balance when status changes"""
        if self.status == "Disbursed" and not self.disbursed_amount:
            self.disbursed_amount = self.loan_amount
            self.balance_amount = self.loan_amount
            self.save()
            
    def generate_repayment_schedule(self):
        """Generate repayment schedule"""
        # Clear existing schedule
        self.repayment_schedule = []
        
        # Generate schedule
        outstanding_balance = self.loan_amount
        monthly_rate = (self.interest_rate / 100) / 12
        due_date = self.repayment_start_date or self.disbursement_date
        
        for i in range(int(self.loan_period_months)):
            due_date = add_months(due_date, 1)
            
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                principal = self.loan_amount / self.loan_period_months
                interest = (self.loan_amount * self.interest_rate / 100) / 12
            else:
                # Reducing balance calculation
                interest = outstanding_balance * monthly_rate
                principal = self.monthly_installment - interest
                
            self.append("repayment_schedule", {
                "payment_date": due_date,
                "principal_amount": principal,
                "interest_amount": interest,
                "total_payment": principal + interest,
                "balance_amount": outstanding_balance - principal
            })
            
            outstanding_balance -= principal
            
        self.save()
        
    def update_member_summary(self):
        """Update member's financial summary"""
        member = frappe.get_doc("SHG Member", self.member)
        member.update_financial_summary()
        
    def send_approval_notification(self):
        """Send loan approval notification"""
        member = frappe.get_doc("SHG Member", self.member)
        
        message = f"Dear {member.member_name}, your loan application of KES {self.loan_amount:,.2f} has been approved."
        
        notification = frappe.get_doc({
            "doctype": "SHG Notification Log",
            "member": self.member,
            "notification_type": "Loan Approval",
            "message": message,
            "channel": "SMS",
            "reference_document": "SHG Loan",
            "reference_name": self.name
        })
        notification.insert()
        
        # Send SMS (would be implemented in actual system)
        # send_sms(member.phone_number, message)

# --- Hook functions ---
def validate_loan(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()


def generate_repayment_schedule(doc, method):
    """Hook function called from hooks.py"""
    if doc.status == "Disbursed":
        doc.generate_repayment_schedule()