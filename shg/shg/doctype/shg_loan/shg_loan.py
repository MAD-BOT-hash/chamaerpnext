import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, getdate, add_months, add_days, flt
import math

class SHGLoan(Document):
    def validate(self):
        self.validate_amount()
        self.validate_interest_rate()
        self.check_member_eligibility()
        self.calculate_repayment_details()
        # Load loan type settings if selected
        if self.loan_type:
            self.load_loan_type_settings()
        
    def validate_amount(self):
        """Validate loan amount"""
        if self.loan_amount <= 0:
            frappe.throw(_("Loan amount must be greater than zero"))
            
    def validate_interest_rate(self):
        """Validate interest rate"""
        if self.interest_rate < 0:
            frappe.throw(_("Interest rate cannot be negative"))
            
    def check_member_eligibility(self):
        """Check if member is eligible for loan"""
        if not self.member:
            frappe.throw(_("Member is required"))
            
        # Check if member exists
        if not frappe.db.exists("SHG Member", self.member):
            frappe.throw(_(f"Member {self.member} does not exist"))
            
        # Get member details
        member = frappe.get_doc("SHG Member", self.member)
        
        # Check if member is active
        if member.membership_status != "Active":
            frappe.throw(_(f"Member {member.member_name} is not active"))
            
        # Check for overdue loans
        overdue_loans = frappe.db.sql("""
            SELECT COUNT(*) 
            FROM `tabSHG Loan` 
            WHERE member = %s 
            AND status = 'Disbursed' 
            AND next_due_date < %s
            AND balance_amount > 0
        """, (self.member, nowdate()))[0][0]
        
        if overdue_loans > 0:
            frappe.throw(_(f"Member {member.member_name} has overdue loans and is not eligible for new loans"))
            
        # Check savings threshold (at least 3 months of contributions)
        settings = frappe.get_single("SHG Settings")
        required_savings = settings.default_contribution_amount * 12  # 12 weeks of contributions
        
        if member.total_contributions < required_savings:
            frappe.throw(_(f"Member {member.member_name} does not meet the minimum savings requirement of KES {required_savings:,.2f}"))
            
    def load_loan_type_settings(self):
        """Load settings from selected loan type"""
        loan_type = frappe.get_doc("SHG Loan Type", self.loan_type)
        if not self.interest_rate:
            self.interest_rate = loan_type.interest_rate
        if not self.interest_type:
            self.interest_type = loan_type.interest_type
        if not self.loan_period_months:
            self.loan_period_months = loan_type.default_tenure_months
        if not self.repayment_frequency:
            self.repayment_frequency = loan_type.repayment_frequency
            
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
        """Generate repayment schedule based on frequency"""
        # Clear existing schedule
        self.repayment_schedule = []
        
        # Generate schedule based on frequency
        if self.repayment_frequency == "Daily":
            self.generate_daily_schedule()
        elif self.repayment_frequency == "Weekly":
            self.generate_weekly_schedule()
        elif self.repayment_frequency == "Bi-Weekly":
            self.generate_biweekly_schedule()
        elif self.repayment_frequency == "Monthly":
            self.generate_monthly_schedule()
        elif self.repayment_frequency == "Bi-Monthly":
            self.generate_bimonthly_schedule()
        elif self.repayment_frequency == "Quarterly":
            self.generate_quarterly_schedule()
        elif self.repayment_frequency == "Yearly":
            self.generate_yearly_schedule()
        else:
            # Default to monthly
            self.generate_monthly_schedule()
            
        self.save()
        
    def generate_daily_schedule(self):
        """Generate daily repayment schedule"""
        outstanding_balance = self.loan_amount
        daily_rate = (self.interest_rate / 100) / 365
        due_date = self.repayment_start_date or self.disbursement_date
        
        # Calculate number of days for the loan period
        total_days = self.loan_period_months * 30  # Approximate
        
        for i in range(total_days):
            due_date = add_days(due_date, 1)
            
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                principal = self.loan_amount / total_days
                interest = (self.loan_amount * self.interest_rate / 100) / 365
            else:
                # Reducing balance calculation
                interest = outstanding_balance * daily_rate
                principal = (self.loan_amount / total_days)  # Simplified
                
            self.append("repayment_schedule", {
                "payment_date": due_date,
                "principal_amount": principal,
                "interest_amount": interest,
                "total_payment": principal + interest,
                "balance_amount": outstanding_balance - principal
            })
            
            outstanding_balance -= principal
            
    def generate_weekly_schedule(self):
        """Generate weekly repayment schedule"""
        outstanding_balance = self.loan_amount
        weekly_rate = (self.interest_rate / 100) / 52
        due_date = self.repayment_start_date or self.disbursement_date
        
        # Calculate number of weeks for the loan period
        total_weeks = self.loan_period_months * 4  # Approximate
        
        for i in range(total_weeks):
            due_date = add_days(due_date, 7)
            
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                principal = self.loan_amount / total_weeks
                interest = (self.loan_amount * self.interest_rate / 100) / 52
            else:
                # Reducing balance calculation
                interest = outstanding_balance * weekly_rate
                principal = (self.loan_amount / total_weeks)  # Simplified
                
            self.append("repayment_schedule", {
                "payment_date": due_date,
                "principal_amount": principal,
                "interest_amount": interest,
                "total_payment": principal + interest,
                "balance_amount": outstanding_balance - principal
            })
            
            outstanding_balance -= principal
            
    def generate_biweekly_schedule(self):
        """Generate bi-weekly repayment schedule"""
        outstanding_balance = self.loan_amount
        biweekly_rate = (self.interest_rate / 100) / 26
        due_date = self.repayment_start_date or self.disbursement_date
        
        # Calculate number of bi-weekly periods for the loan period
        total_biweekly = self.loan_period_months * 2  # Approximate
        
        for i in range(total_biweekly):
            due_date = add_days(due_date, 14)
            
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                principal = self.loan_amount / total_biweekly
                interest = (self.loan_amount * self.interest_rate / 100) / 26
            else:
                # Reducing balance calculation
                interest = outstanding_balance * biweekly_rate
                principal = (self.loan_amount / total_biweekly)  # Simplified
                
            self.append("repayment_schedule", {
                "payment_date": due_date,
                "principal_amount": principal,
                "interest_amount": interest,
                "total_payment": principal + interest,
                "balance_amount": outstanding_balance - principal
            })
            
            outstanding_balance -= principal
            
    def generate_monthly_schedule(self):
        """Generate monthly repayment schedule"""
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
            
    def generate_bimonthly_schedule(self):
        """Generate bi-monthly repayment schedule"""
        outstanding_balance = self.loan_amount
        bimonthly_rate = (self.interest_rate / 100) / 6  # 6 periods per year
        due_date = self.repayment_start_date or self.disbursement_date
        
        # Calculate number of bi-monthly periods for the loan period
        total_bimonthly = self.loan_period_months / 2
        
        for i in range(int(total_bimonthly)):
            due_date = add_months(due_date, 2)
            
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                principal = self.loan_amount / total_bimonthly
                interest = (self.loan_amount * self.interest_rate / 100) / 6
            else:
                # Reducing balance calculation
                interest = outstanding_balance * bimonthly_rate
                principal = (self.loan_amount / total_bimonthly)  # Simplified
                
            self.append("repayment_schedule", {
                "payment_date": due_date,
                "principal_amount": principal,
                "interest_amount": interest,
                "total_payment": principal + interest,
                "balance_amount": outstanding_balance - principal
            })
            
            outstanding_balance -= principal
            
    def generate_quarterly_schedule(self):
        """Generate quarterly repayment schedule"""
        outstanding_balance = self.loan_amount
        quarterly_rate = (self.interest_rate / 100) / 4
        due_date = self.repayment_start_date or self.disbursement_date
        
        # Calculate number of quarterly periods for the loan period
        total_quarterly = self.loan_period_months / 3
        
        for i in range(int(total_quarterly)):
            due_date = add_months(due_date, 3)
            
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                principal = self.loan_amount / total_quarterly
                interest = (self.loan_amount * self.interest_rate / 100) / 4
            else:
                # Reducing balance calculation
                interest = outstanding_balance * quarterly_rate
                principal = (self.loan_amount / total_quarterly)  # Simplified
                
            self.append("repayment_schedule", {
                "payment_date": due_date,
                "principal_amount": principal,
                "interest_amount": interest,
                "total_payment": principal + interest,
                "balance_amount": outstanding_balance - principal
            })
            
            outstanding_balance -= principal
            
    def generate_yearly_schedule(self):
        """Generate yearly repayment schedule"""
        outstanding_balance = self.loan_amount
        yearly_rate = (self.interest_rate / 100)
        due_date = self.repayment_start_date or self.disbursement_date
        
        # Calculate number of yearly periods for the loan period
        total_yearly = self.loan_period_months / 12
        
        for i in range(int(total_yearly)):
            due_date = add_months(due_date, 12)
            
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                principal = self.loan_amount / total_yearly
                interest = (self.loan_amount * self.interest_rate / 100)
            else:
                # Reducing balance calculation
                interest = outstanding_balance * yearly_rate
                principal = (self.loan_amount / total_yearly)  # Simplified
                
            self.append("repayment_schedule", {
                "payment_date": due_date,
                "principal_amount": principal,
                "interest_amount": interest,
                "total_payment": principal + interest,
                "balance_amount": outstanding_balance - principal
            })
            
            outstanding_balance -= principal
            
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