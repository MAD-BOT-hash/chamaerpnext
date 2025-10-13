import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, getdate, add_months, add_days, flt
import math

class SHGLoan(Document):
    def validate(self):
        """Round numeric fields before save."""
        if self.loan_amount:
            self.loan_amount = round(flt(self.loan_amount), 2)
        if self.monthly_installment:
            self.monthly_installment = round(flt(self.monthly_installment), 2)
        if self.total_payable:
            self.total_payable = round(flt(self.total_payable), 2)
        if self.balance_amount:
            self.balance_amount = round(flt(self.balance_amount), 2)
        if self.disbursed_amount:
            self.disbursed_amount = round(flt(self.disbursed_amount), 2)
        if self.total_repaid:
            self.total_repaid = round(flt(self.total_repaid), 2)
        if self.overdue_amount:
            self.overdue_amount = round(flt(self.overdue_amount), 2)

        # Auto populate repayment schedule if missing
        if not self.repayment_schedule or len(self.repayment_schedule) == 0:
            self.generate_repayment_schedule()
            
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
            
    @frappe.whitelist()
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
        """Calculate repayment details with improved accuracy"""
        if self.loan_amount and self.interest_rate and self.loan_period_months:
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                total_interest = self.loan_amount * (self.interest_rate / 100) * (self.loan_period_months / 12)
                self.total_payable = self.loan_amount + total_interest
                if self.loan_period_months > 0:
                    self.monthly_installment = self.total_payable / self.loan_period_months
                else:
                    self.monthly_installment = 0
                
                # Ensure monetary values are rounded to 2 decimal places
                if self.total_payable:
                    self.total_payable = round(float(self.total_payable), 2)
                if self.monthly_installment:
                    self.monthly_installment = round(float(self.monthly_installment), 2)
            else:
                # Reducing balance calculation using standard formula
                monthly_rate = (self.interest_rate / 100) / 12
                if monthly_rate > 0 and self.loan_period_months > 0:
                    # Standard amortization formula
                    self.monthly_installment = (self.loan_amount * monthly_rate * 
                                             (1 + monthly_rate) ** self.loan_period_months) / \
                                             ((1 + monthly_rate) ** self.loan_period_months - 1)
                elif self.loan_period_months > 0:
                    # No interest loan
                    self.monthly_installment = self.loan_amount / self.loan_period_months
                else:
                    self.monthly_installment = 0
                    
                # For display purposes, calculate total payable
                self.total_payable = self.monthly_installment * self.loan_period_months
                
            # Ensure monetary values are rounded to 2 decimal places
            if self.monthly_installment:
                self.monthly_installment = round(float(self.monthly_installment), 2)
            if self.total_payable:
                self.total_payable = round(float(self.total_payable), 2)
                
    def generate_repayment_schedule(self):
        """
        Generate repayment schedule with principal, interest, and total per installment.
        Supports flat and reducing balance interest types.
        """
        if not self.loan_amount or not self.loan_period_months or not self.interest_rate:
            frappe.throw("Please set Loan Amount, Repayment Periods, and Interest Rate before generating schedule.")

        # Clean existing child table
        self.set("repayment_schedule", [])

        principal = flt(self.loan_amount)
        rate = flt(self.interest_rate) / 100
        months = int(self.loan_period_months)
        balance = principal

        # Interest mode — default to Flat if not specified
        interest_type = self.interest_type or "Flat Rate"

        # Calculate flat interest per month
        if interest_type == "Flat Rate":
            monthly_interest = (principal * rate) / 12
            principal_component = principal / months
        else:
            # Reducing balance: interest recalculated each month
            monthly_interest = 0
            principal_component = principal / months

        # Start date for first installment
        start_date = getdate(self.repayment_start_date or self.disbursement_date or frappe.utils.nowdate())

        total_interest = 0.0
        total_payment = 0.0

        for i in range(months):
            if interest_type == "Reducing Balance":
                interest_component = (balance * rate) / 12
            else:
                interest_component = monthly_interest

            principal_paid = principal_component
            total_installment = principal_paid + interest_component
            balance = max(balance - principal_paid, 0)

            total_interest += flt(interest_component)
            total_payment += flt(total_installment)

            self.append("repayment_schedule", {
                "payment_date": add_months(start_date, i + 1),
                "principal_amount": round(flt(principal_paid), 2),
                "interest_amount": round(flt(interest_component), 2),
                "total_payment": round(flt(total_installment), 2),
                "balance_amount": round(flt(balance), 2)
            })

        # Update totals on parent loan
        self.total_interest_payable = round(total_interest, 2)
        self.total_payable_amount = round(total_payment, 2)
        self.monthly_installment = round(total_payment / months, 2)

        frappe.msgprint(f"✅ Repayment schedule generated successfully for {months} months.")
                
    def before_save(self):
        """Ensure all numeric fields are rounded."""
        for field in ["loan_amount", "monthly_installment", "total_payable", "balance_amount", "disbursed_amount", "total_repaid", "overdue_amount"]:
            if getattr(self, field, None):
                setattr(self, field, round(flt(getattr(self, field)), 2))
                
    def validate_accounts(self):
        """Validate account mappings"""
        if not self.account_mapping:
            frappe.throw(_("Please set up account mappings for this loan type"))
            
        # Check for duplicate accounts
        accounts = [row.account for row in self.account_mapping]
        if len(accounts) != len(set(accounts)):
            frappe.throw(_("Duplicate accounts found in account mapping"))
            
    def update_loan_summary(self):
        """Update loan summary fields"""
        # Calculate total repaid
        total_repaid = frappe.db.sql("""
            SELECT SUM(total_paid)
            FROM `tabSHG Loan Repayment`
            WHERE loan = %s AND docstatus = 1
        """, self.name)[0][0] or 0
        
        self.total_repaid = total_repaid
        self.balance_amount = max(0, self.loan_amount - self.total_repaid)
        
        # Calculate overdue amount
        if self.next_due_date and getdate(self.next_due_date) < getdate() and self.balance_amount > 0:
            self.overdue_amount = self.balance_amount
        else:
            self.overdue_amount = 0
            
        # Update member summary
        if self.member:
            member = frappe.get_doc("SHG Member", self.member)
            member.update_financial_summary()

# --- Hook functions ---
# These are hook functions called from hooks.py and should NOT have @frappe.whitelist()
def validate_loan(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()

def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    if doc.docstatus == 1 and not doc.get("posted_to_gl"):
        doc.post_to_ledger()