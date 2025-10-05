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
            monthly_interest = None
            principal_component = principal / months

        # Start date for first installment
        start_date = getdate(self.repayment_start_date or self.disbursement_date or frappe.utils.nowdate())

        total_interest = 0
        total_payment = 0

        for i in range(months):
            if interest_type == "Reducing Balance":
                interest_component = (balance * rate) / 12
            else:
                interest_component = monthly_interest

            principal_paid = principal_component
            total_installment = principal_paid + interest_component
            balance = max(balance - principal_paid, 0)

            total_interest += interest_component
            total_payment += total_installment

            self.append("repayment_schedule", {
                "payment_date": add_months(start_date, i + 1),
                "principal_amount": round(principal_paid, 2),
                "interest_amount": round(interest_component, 2),
                "total_payment": round(total_installment, 2),
                "balance_amount": round(balance, 2)
            })

        # Update totals on parent loan
        self.total_interest_payable = round(total_interest, 2)
        self.total_payable_amount = round(total_payment, 2)
        self.monthly_installment = round(total_payment / months, 2)

        frappe.msgprint(f"✅ Repayment schedule generated successfully for {months} months.")
                
    def before_save(self):
        """Ensure all numeric fields are rounded."""
        for field in ["loan_amount", "monthly_installment", "total_payable", "balance_amount", "disbursed_amount"]:
            if getattr(self, field, None):
                setattr(self, field, round(flt(getattr(self, field)), 2))
                
    @frappe.whitelist()
    def disburse_loan(self):
        """Disburse the loan and create accounting entries."""
        if self.status != "Approved":
            frappe.throw("Loan must be Approved before disbursement.")
        
        # Check for existing Journal Entry
        existing_je = frappe.db.exists("Journal Entry Account", {"reference_name": self.name, "reference_type": "Loan"})
        if existing_je:
            frappe.msgprint(f"Loan {self.name} already disbursed via Journal Entry {existing_je}")
            return
        
        # Get company
        company = frappe.defaults.get_user_default("Company")
        if not company:
            companies = frappe.get_all("Company", limit=1)
            if companies:
                company = companies[0].name
            else:
                frappe.throw(_("Please create a company first"))

        # Get Accounts
        debit_account = self.get_loan_account(company)  # Loans Receivable account
        credit_account = self.get_bank_account(company)  # Cash/Bank account

        je = frappe.new_doc("Journal Entry")
        je.posting_date = frappe.utils.nowdate()
        je.voucher_type = "Bank Entry"
        je.user_remark = f"Loan disbursement for {self.member_name or self.member} ({self.name})"
        
        # Debit member loan receivable
        je.append("accounts", {
            "account": debit_account,
            "party_type": "Customer",
            "party": self.get_member_customer(),
            "debit_in_account_currency": self.loan_amount,
            "reference_type": "Loan",
            "reference_name": self.name
        })
        
        # Credit the bank or cash account
        je.append("accounts", {
            "account": credit_account,
            "credit_in_account_currency": self.loan_amount,
            "reference_type": "Loan",
            "reference_name": self.name
        })
        
        je.insert(ignore_permissions=True)
        je.submit()

        # Update loan status
        self.db_set("status", "Disbursed")
        self.db_set("disbursement_journal_entry", je.name)
        self.db_set("disbursed_amount", self.loan_amount)
        self.db_set("balance_amount", self.loan_amount)

        frappe.msgprint(f"Loan {self.name} successfully disbursed. Journal Entry: {je.name}")

    def before_cancel(self):
        """
        Allow cancelling a loan only if not yet disbursed.
        Clean up related repayment schedules, journal entries, and payments.
        Reset member eligibility and overdue status.
        """
        if self.status == "Disbursed":
            frappe.throw("You cannot cancel a loan that has already been disbursed.")

        frappe.msgprint(f"🧹 Cancelling Loan {self.name} — cleaning up related records...")

        # Delete related repayment schedules
        try:
            schedules = frappe.get_all("SHG Loan Repayment Schedule", {"parent": self.name})
            for s in schedules:
                try:
                    frappe.delete_doc("SHG Loan Repayment Schedule", s.name, force=True, ignore_permissions=True)
                except Exception as e:
                    frappe.log_error(f"Error deleting SHG Loan Repayment Schedule {s.name}: {e}")
        except Exception as e:
            frappe.log_error(f"Error fetching SHG Loan Repayment Schedules for {self.name}: {e}")

        # Cancel and delete related Journal Entries
        try:
            jes = frappe.get_all("Journal Entry Account", {"reference_name": self.name, "reference_type": "Loan"}, pluck="parent")
            for je in jes:
                try:
                    doc = frappe.get_doc("Journal Entry", je)
                    if doc.docstatus == 1:
                        doc.cancel()
                    frappe.delete_doc("Journal Entry", je, force=True, ignore_permissions=True)
                except Exception as e:
                    frappe.log_error(f"Error deleting Journal Entry {je}: {e}")
        except Exception as e:
            frappe.log_error(f"Error fetching Journal Entries for {self.name}: {e}")

        # Cancel and delete related Payment Entries
        try:
            pes = frappe.get_all("Payment Entry Reference", {"reference_name": self.name, "reference_doctype": "SHG Loan"}, pluck="parent")
            for pe in pes:
                try:
                    doc = frappe.get_doc("Payment Entry", pe)
                    if doc.docstatus == 1:
                        doc.cancel()
                    frappe.delete_doc("Payment Entry", pe, force=True, ignore_permissions=True)
                except Exception as e:
                    frappe.log_error(f"Error deleting Payment Entry {pe}: {e}")
        except Exception as e:
            frappe.log_error(f"Error fetching Payment Entries for {self.name}: {e}")

        # Reset loan eligibility and overdue flag for member
        if self.member:
            # Safe lookup to ensure member exists
            if frappe.db.exists("SHG Member", self.member):
                frappe.msgprint(f"🔄 Resetting eligibility for member {self.member}")
                
                # Reset flags directly in SHG Member
                try:
                    frappe.db.set_value("SHG Member", self.member, {
                        "loan_eligibility_flag": 1,
                        "has_overdue_loans": 0
                    })
                except Exception as e:
                    frappe.log_error(f"Error updating eligibility flags for member {self.member}: {e}")

                # Optional: Update Financial Summary if it exists
                try:
                    if frappe.db.exists("DocType", "SHG Financial Summary"):
                        try:
                            summary = frappe.get_all("SHG Financial Summary", {"member": self.member}, pluck="name")
                            if summary:
                                summary_doc = frappe.get_doc("SHG Financial Summary", summary[0])
                                summary_doc.total_outstanding_loans = 0
                                summary_doc.total_overdue_amount = 0
                                summary_doc.save(ignore_permissions=True)
                            else:
                                frappe.msgprint("⚠️ Financial Summary record not found, skipped.")
                        except Exception as e:
                            frappe.log_error(f"Error updating Financial Summary for member {self.member}: {e}", "SHG Loan Cancel Cleanup Warning")
                            frappe.msgprint("⚠️ Financial Summary record not found, skipped.")
                    else:
                        frappe.msgprint("⚠️ Financial Summary record not found, skipped.")
                except Exception as e:
                    frappe.log_error(f"Error checking Financial Summary doctype: {e}", "SHG Loan Cancel Cleanup Warning")
                    frappe.msgprint("⚠️ Financial Summary record not found, skipped.")

                frappe.msgprint(f"✅ Member eligibility reset for {self.member}")
            else:
                frappe.msgprint(f"⚠️ Member {self.member} not found, skipping eligibility reset.")

    def before_trash(self):
        """
        Allow deletion only if loan is not disbursed.
        """
        if self.status == "Disbursed":
            frappe.throw("You cannot delete a disbursed loan record.")
                
    def on_update_after_submit(self):
        """
        Allow limited status transitions after submit.
        """
        allowed_fields = ["status"]

        # Restrict edits
        for field in self.get_dirty_fields():
            if field not in allowed_fields:
                frappe.throw(f"Not allowed to change {field} after submission.")

        old_status = self.get_db_value("status")

        # Auto-disburse when moving from Approved to Disbursed
        if old_status == "Approved" and self.status == "Disbursed":
            self.disburse_loan()
        else:
            frappe.msgprint(f"Status updated from {old_status} → {self.status}")
                
    def on_submit(self):
        if self.status == "Approved":
            self.generate_repayment_schedule()
            self.update_member_summary()
            self.send_approval_notification()
        elif self.status == "Disbursed":
            self.generate_repayment_schedule()
            self.update_member_summary()
            # Disburse the loan
            self.disburse_loan()
            # ensure idempotent: if already posted -> skip
            if not self.get("posted_to_gl"):
                self.post_to_ledger()
            self.validate_gl_entries()
            
    def on_update(self):
        """Update balance when status changes"""
        if self.status == "Disbursed" and not self.disbursed_amount:
            # Disburse the loan if not already done
            if not self.disbursement_journal_entry:
                self.disburse_loan()
            else:
                self.disbursed_amount = self.loan_amount
                self.balance_amount = self.loan_amount
                # Set next due date based on repayment frequency
                if self.repayment_frequency == "Daily":
                    self.next_due_date = add_days(getdate(self.disbursement_date or nowdate()), 1)
                elif self.repayment_frequency == "Weekly":
                    self.next_due_date = add_days(getdate(self.disbursement_date or nowdate()), 7)
                elif self.repayment_frequency == "Bi-Weekly":
                    self.next_due_date = add_days(getdate(self.disbursement_date or nowdate()), 14)
                elif self.repayment_frequency == "Monthly":
                    self.next_due_date = add_months(getdate(self.disbursement_date or nowdate()), 1)
                elif self.repayment_frequency == "Bi-Monthly":
                    self.next_due_date = add_months(getdate(self.disbursement_date or nowdate()), 2)
                elif self.repayment_frequency == "Quarterly":
                    self.next_due_date = add_months(getdate(self.disbursement_date or nowdate()), 3)
                elif self.repayment_frequency == "Yearly":
                    self.next_due_date = add_months(getdate(self.disbursement_date or nowdate()), 12)
                else:
                    # Default to monthly
                    self.next_due_date = add_months(getdate(self.disbursement_date or nowdate()), 1)
                self.save()
            
    def validate_gl_entries(self):
        """Validate that GL entries were created properly"""
        if not self.disbursement_journal_entry and not self.disbursement_payment_entry:
            frappe.throw(_("Failed to create Journal Entry or Payment Entry for this loan disbursement. Please check the system logs."))
            
        # Use validation utilities
        from shg.shg.utils.validation_utils import validate_reference_types_and_names, validate_custom_field_linking, validate_accounting_integrity
        validate_reference_types_and_names(self)
        validate_custom_field_linking(self)
        validate_accounting_integrity(self)
            
    def post_to_ledger(self):
        """
        Create a Payment Entry for this loan disbursement.
        """
        from shg.shg.utils.gl_utils import create_loan_disbursement_payment_entry, update_document_with_payment_entry
        payment_entry = create_loan_disbursement_payment_entry(self)
        update_document_with_payment_entry(self, payment_entry, "disbursement_payment_entry")
        
    def get_member_account(self):
        """Get member's ledger account, create if not exists"""
        member = frappe.get_doc("SHG Member", self.member)
        company = frappe.defaults.get_user_default("Company")
        if not company:
            companies = frappe.get_all("Company", limit=1)
            if companies:
                company = companies[0].name
            else:
                frappe.throw(_("Please create a company first"))
                
        from shg.shg.utils.account_utils import get_or_create_member_account
        return get_or_create_member_account(member, company)
        
    def get_loan_account(self, company):
        """Get loan account, create if not exists"""
        from shg.shg.utils.account_utils import get_or_create_shg_loans_account
        return get_or_create_shg_loans_account(company)
        
    def get_bank_account(self, company):
        """Get bank account from settings or defaults"""
        settings = frappe.get_single("SHG Settings")
        if settings.default_bank_account:
            return settings.default_bank_account
        else:
            # Try to find a default bank account
            bank_accounts = frappe.get_all("Account", filters={
                "company": company,
                "account_type": "Bank",
                "is_group": 0
            }, limit=1)
            if bank_accounts:
                return bank_accounts[0].name
            else:
                frappe.throw(_("Please configure default bank account in SHG Settings"))
        
    def get_member_customer(self):
        """Get member's customer link"""
        member = frappe.get_doc("SHG Member", self.member)
        return member.customer
                
    def generate_daily_schedule(self):
        """Generate daily repayment schedule"""
        outstanding_balance = self.loan_amount
        daily_rate = (self.interest_rate / 100) / 365
        due_date = self.repayment_start_date or self.disbursement_date
        
        # Calculate number of days for the loan period
        total_days = int(self.loan_period_months * 30)  # Approximate
        
        if total_days <= 0:
            return
            
        for i in range(total_days):
            due_date = add_days(due_date, 1)
            
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                principal = self.loan_amount / total_days
                interest = (self.loan_amount * self.interest_rate / 100) / 365
            else:
                # Reducing balance calculation
                interest = outstanding_balance * daily_rate
                # For daily payments, principal is calculated to ensure loan is paid off
                if i == total_days - 1:
                    # Last payment - pay off remaining balance
                    principal = outstanding_balance
                else:
                    principal = self.monthly_installment / 30 if self.monthly_installment > 0 else 0
                
            self.append("repayment_schedule", {
                "payment_date": due_date,
                "principal_amount": principal,
                "interest_amount": interest,
                "total_payment": principal + interest,
                "balance_amount": max(0, outstanding_balance - principal)
            })
            
            outstanding_balance = max(0, outstanding_balance - principal)
            if outstanding_balance <= 0:
                break
            
    def generate_weekly_schedule(self):
        """Generate weekly repayment schedule"""
        outstanding_balance = self.loan_amount
        weekly_rate = (self.interest_rate / 100) / 52
        due_date = self.repayment_start_date or self.disbursement_date
        
        # Calculate number of weeks for the loan period
        total_weeks = int(self.loan_period_months * 4)  # Approximate
        
        if total_weeks <= 0:
            return
            
        weekly_installment = self.monthly_installment * 12 / 52 if self.monthly_installment > 0 else 0
        
        for i in range(total_weeks):
            due_date = add_days(due_date, 7)
            
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                principal = self.loan_amount / total_weeks
                interest = (self.loan_amount * self.interest_rate / 100) / 52
            else:
                # Reducing balance calculation
                interest = outstanding_balance * weekly_rate
                # For weekly payments
                if i == total_weeks - 1:
                    # Last payment - pay off remaining balance
                    principal = outstanding_balance
                else:
                    principal = weekly_installment - interest if weekly_installment > interest else 0
                
            self.append("repayment_schedule", {
                "payment_date": due_date,
                "principal_amount": principal,
                "interest_amount": interest,
                "total_payment": principal + interest,
                "balance_amount": max(0, outstanding_balance - principal)
            })
            
            outstanding_balance = max(0, outstanding_balance - principal)
            if outstanding_balance <= 0:
                break
            
    def generate_biweekly_schedule(self):
        """Generate bi-weekly repayment schedule"""
        outstanding_balance = self.loan_amount
        biweekly_rate = (self.interest_rate / 100) / 26
        due_date = self.repayment_start_date or self.disbursement_date
        
        # Calculate number of bi-weekly periods for the loan period
        total_biweekly = int(self.loan_period_months * 2)  # Approximate
        
        if total_biweekly <= 0:
            return
            
        biweekly_installment = self.monthly_installment * 12 / 26 if self.monthly_installment > 0 else 0
        
        for i in range(total_biweekly):
            due_date = add_days(due_date, 14)
            
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                principal = self.loan_amount / total_biweekly
                interest = (self.loan_amount * self.interest_rate / 100) / 26
            else:
                # Reducing balance calculation
                interest = outstanding_balance * biweekly_rate
                # For bi-weekly payments
                if i == total_biweekly - 1:
                    # Last payment - pay off remaining balance
                    principal = outstanding_balance
                else:
                    principal = biweekly_installment - interest if biweekly_installment > interest else 0
                
            self.append("repayment_schedule", {
                "payment_date": due_date,
                "principal_amount": principal,
                "interest_amount": interest,
                "total_payment": principal + interest,
                "balance_amount": max(0, outstanding_balance - principal)
            })
            
            outstanding_balance = max(0, outstanding_balance - principal)
            if outstanding_balance <= 0:
                break
            
    def generate_monthly_schedule(self):
        """Generate monthly repayment schedule with improved accuracy"""
        outstanding_balance = self.loan_amount
        monthly_rate = (self.interest_rate / 100) / 12
        due_date = self.repayment_start_date or self.disbursement_date
        
        total_months = int(self.loan_period_months)
        
        if total_months <= 0:
            return
            
        for i in range(total_months):
            due_date = add_months(due_date, 1)
            
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                principal = self.loan_amount / total_months
                interest = (self.loan_amount * self.interest_rate / 100) / 12
            else:
                # Reducing balance calculation using the proper amortization formula
                interest = outstanding_balance * monthly_rate
                # For monthly payments
                if i == total_months - 1:
                    # Last payment - pay off remaining balance
                    principal = outstanding_balance
                else:
                    principal = self.monthly_installment - interest if self.monthly_installment > interest else 0
                
            self.append("repayment_schedule", {
                "payment_date": due_date,
                "principal_amount": principal,
                "interest_amount": interest,
                "total_payment": principal + interest,
                "balance_amount": max(0, outstanding_balance - principal)
            })
            
            outstanding_balance = max(0, outstanding_balance - principal)
            if outstanding_balance <= 0:
                break
            
    def generate_bimonthly_schedule(self):
        """Generate bi-monthly repayment schedule"""
        outstanding_balance = self.loan_amount
        bimonthly_rate = (self.interest_rate / 100) / 6  # 6 periods per year
        due_date = self.repayment_start_date or self.disbursement_date
        
        # Calculate number of bi-monthly periods for the loan period
        total_bimonthly = int(self.loan_period_months / 2)
        
        if total_bimonthly <= 0:
            return
            
        bimonthly_installment = self.monthly_installment * 2 if self.monthly_installment > 0 else 0
        
        for i in range(total_bimonthly):
            due_date = add_months(due_date, 2)
            
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                principal = self.loan_amount / total_bimonthly
                interest = (self.loan_amount * self.interest_rate / 100) / 6
            else:
                # Reducing balance calculation
                interest = outstanding_balance * bimonthly_rate
                # For bi-monthly payments
                if i == total_bimonthly - 1:
                    # Last payment - pay off remaining balance
                    principal = outstanding_balance
                else:
                    principal = bimonthly_installment - interest if bimonthly_installment > interest else 0
                
            self.append("repayment_schedule", {
                "payment_date": due_date,
                "principal_amount": principal,
                "interest_amount": interest,
                "total_payment": principal + interest,
                "balance_amount": max(0, outstanding_balance - principal)
            })
            
            outstanding_balance = max(0, outstanding_balance - principal)
            if outstanding_balance <= 0:
                break
            
    def generate_quarterly_schedule(self):
        """Generate quarterly repayment schedule"""
        outstanding_balance = self.loan_amount
        quarterly_rate = (self.interest_rate / 100) / 4
        due_date = self.repayment_start_date or self.disbursement_date
        
        # Calculate number of quarterly periods for the loan period
        total_quarterly = int(self.loan_period_months / 3)
        
        if total_quarterly <= 0:
            return
            
        quarterly_installment = self.monthly_installment * 3 if self.monthly_installment > 0 else 0
        
        for i in range(total_quarterly):
            due_date = add_months(due_date, 3)
            
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                principal = self.loan_amount / total_quarterly
                interest = (self.loan_amount * self.interest_rate / 100) / 4
            else:
                # Reducing balance calculation
                interest = outstanding_balance * quarterly_rate
                # For quarterly payments
                if i == total_quarterly - 1:
                    # Last payment - pay off remaining balance
                    principal = outstanding_balance
                else:
                    principal = quarterly_installment - interest if quarterly_installment > interest else 0
                
            self.append("repayment_schedule", {
                "payment_date": due_date,
                "principal_amount": principal,
                "interest_amount": interest,
                "total_payment": principal + interest,
                "balance_amount": max(0, outstanding_balance - principal)
            })
            
            outstanding_balance = max(0, outstanding_balance - principal)
            if outstanding_balance <= 0:
                break
            
    def generate_yearly_schedule(self):
        """Generate yearly repayment schedule"""
        outstanding_balance = self.loan_amount
        yearly_rate = (self.interest_rate / 100)
        due_date = self.repayment_start_date or self.disbursement_date
        
        # Calculate number of yearly periods for the loan period
        total_yearly = int(self.loan_period_months / 12)
        
        if total_yearly <= 0:
            return
            
        yearly_installment = self.monthly_installment * 12 if self.monthly_installment > 0 else 0
        
        for i in range(total_yearly):
            due_date = add_months(due_date, 12)
            
            if self.interest_type == "Flat Rate":
                # Flat rate calculation
                principal = self.loan_amount / total_yearly
                interest = (self.loan_amount * self.interest_rate / 100)
            else:
                # Reducing balance calculation
                interest = outstanding_balance * yearly_rate
                # For yearly payments
                if i == total_yearly - 1:
                    # Last payment - pay off remaining balance
                    principal = outstanding_balance
                else:
                    principal = yearly_installment - interest if yearly_installment > interest else 0
                
            self.append("repayment_schedule", {
                "payment_date": due_date,
                "principal_amount": principal,
                "interest_amount": interest,
                "total_payment": principal + interest,
                "balance_amount": max(0, outstanding_balance - principal)
            })
            
            outstanding_balance = max(0, outstanding_balance - principal)
            if outstanding_balance <= 0:
                break
            
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
# These are hook functions called from hooks.py and should NOT have @frappe.whitelist()
def validate_loan(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()


def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    if doc.docstatus == 1 and doc.status == "Disbursed" and not doc.get("posted_to_gl"):
        doc.post_to_ledger()


def generate_repayment_schedule(doc, method):
    """Hook function called from hooks.py"""
    if doc.status == "Disbursed":
        doc.generate_repayment_schedule()


@frappe.whitelist()
def disburse_loan(docname):
    """Public API to disburse a loan manually from button or client script"""
    loan = frappe.get_doc("SHG Loan", docname)
    loan.disburse_loan()
    return "Loan disbursed successfully."


@frappe.whitelist()
def cancel_loan_and_cleanup(docname):
    """
    Cancel a submitted SHG Loan, delete related Payment Entries and Repayment Schedules,
    and reset member eligibility safely (only if SHG Financial Summary exists).
    """
    try:
        loan = frappe.get_doc("SHG Loan", docname)

        if loan.docstatus != 1:
            frappe.throw(f"Loan {docname} must be submitted before cancellation.")

        frappe.msgprint(f"🧹 Cancelling Loan {docname} — removing related records and resetting member eligibility...")

        # Cancel related Payment Entries
        pes = frappe.get_all("Payment Entry Reference", {"reference_name": docname, "reference_doctype": "SHG Loan"}, pluck="parent")
        for pe in pes:
            try:
                doc = frappe.get_doc("Payment Entry", pe)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc("Payment Entry", pe, force=True, ignore_permissions=True)
            except Exception as e:
                frappe.log_error(f"Error cancelling/deleting Payment Entry {pe}: {e}")

        # Cancel related Journal Entries
        jes = frappe.get_all("Journal Entry Account", {"reference_name": docname, "reference_type": "Loan"}, pluck="parent")
        for je in jes:
            try:
                doc = frappe.get_doc("Journal Entry", je)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc("Journal Entry", je, force=True, ignore_permissions=True)
            except Exception as e:
                frappe.log_error(f"Error cancelling/deleting Journal Entry {je}: {e}")

        # Remove repayment schedules
        frappe.db.delete("SHG Loan Repayment Schedule", {"parent": docname})

        # Reset eligibility safely in SHG Member
        if loan.member:
            frappe.msgprint(f"🔄 Resetting eligibility for member {loan.member}")
            
            # Reset flags directly in SHG Member
            frappe.db.set_value("SHG Member", loan.member, {
                "loan_eligibility_flag": 1,
                "has_overdue_loans": 0
            })

            # Optional: Update Financial Summary if it exists
            try:
                if frappe.db.exists("DocType", "SHG Financial Summary"):
                    summary = frappe.get_all("SHG Financial Summary", {"member": loan.member}, pluck="name")
                    if summary:
                        summary_doc = frappe.get_doc("SHG Financial Summary", summary[0])
                        summary_doc.total_outstanding_loans = 0
                        summary_doc.total_overdue_amount = 0
                        summary_doc.save(ignore_permissions=True)
                        frappe.msgprint(f"✅ Member {loan.member} eligibility restored and financial summary cleared.")
                    else:
                        frappe.msgprint(f"⚠️ No Financial Summary found for {loan.member} — skipping reset.")
                else:
                    frappe.msgprint(f"⚠️ SHG Financial Summary doctype not found — skipping reset.")
            except Exception as e:
                frappe.log_error(f"Error updating Financial Summary for member {loan.member}: {e}", "SHG Loan Cancel Cleanup Warning")
                frappe.msgprint(f"⚠️ Error updating Financial Summary for {loan.member} — skipping reset.")

        # Finally cancel the loan
        loan.cancel()

        frappe.db.commit()
        frappe.msgprint(f"✅ Loan {docname} and related records successfully cancelled and cleaned up.")
        return "Loan cancelled and cleaned up successfully."

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG Loan Cancel Error")
        frappe.throw(f"Error while cancelling loan {docname}: {str(e)}")