import frappe
from frappe.model.document import Document
from frappe.utils import flt, today, getdate, add_months

class SHGLoanRepayment(Document):
    def validate(self):
        """Validate repayment details"""
        self.get_loan_details()
        self.calculate_repayment_breakdown()
        self.validate_repayment_amount()
        self.validate_loan_status()
        
        # Ensure monetary values are rounded to 2 decimal places
        if self.total_paid:
            self.total_paid = round(float(self.total_paid), 2)
        if self.principal_amount:
            self.principal_amount = round(float(self.principal_amount), 2)
        if self.interest_amount:
            self.interest_amount = round(float(self.interest_amount), 2)
        if self.penalty_amount:
            self.penalty_amount = round(float(self.penalty_amount), 2)
        if self.balance_after_payment:
            self.balance_after_payment = round(float(self.balance_after_payment), 2)

    def validate_repayment_amount(self):
        if self.total_paid <= 0:
            frappe.throw("Repayment amount must be greater than zero")

        if self.loan:
            loan = frappe.get_doc("SHG Loan", self.loan)
            # More accurate validation based on actual loan balance
            max_payment = loan.balance_amount * 1.1  # Allow 10% buffer for interest/penalties

            if self.total_paid > max_payment:
                frappe.msgprint(
                    f"Warning: Payment {self.total_paid} exceeds maximum expected {max_payment}",
                    alert=True
                )

    def validate_loan_status(self):
        if self.loan:
            loan = frappe.get_doc("SHG Loan", self.loan)
            if loan.status != "Disbursed":
                frappe.throw(f"Cannot record repayment. Loan status is '{loan.status}'.")
            if loan.balance_amount <= 0:
                frappe.throw("Loan is already fully paid.")

    # --------------------
    # Core Loan Logic
    # --------------------

    def get_loan_details(self):
        """Get loan details"""
        if self.loan:
            loan = frappe.get_doc("SHG Loan", self.loan)
            self.member = loan.member
            self.member_name = loan.member_name
            self.outstanding_balance = loan.balance_amount

    def calculate_repayment_breakdown(self):
        """Calculate principal, interest, and penalty breakdown with improved accuracy"""
        if not self.loan:
            return
            
        loan = frappe.get_doc("SHG Loan", self.loan)

        # Calculate penalties based on overdue status
        penalty_amount = 0
        if loan.next_due_date and getdate(self.repayment_date) > getdate(loan.next_due_date):
            overdue_days = (getdate(self.repayment_date) - getdate(loan.next_due_date)).days
            # Penalty calculation: 5% per month on outstanding balance
            penalty_rate = 0.05  # 5% per month
            penalty_amount = loan.balance_amount * penalty_rate * (overdue_days / 30)
        
        self.penalty_amount = penalty_amount

        # Calculate interest based on loan type
        if loan.interest_type == "Flat Rate":
            # For flat rate loans, interest is calculated on original principal
            monthly_interest = (loan.loan_amount * (loan.interest_rate / 100)) / 12
        else:
            # For reducing balance loans, interest is calculated on current balance
            monthly_interest = loan.balance_amount * (loan.interest_rate / 100) / 12

        # Allocate payment: First penalty, then interest, then principal
        remaining_amount = self.total_paid

        # Deduct penalty
        penalty_paid = min(remaining_amount, self.penalty_amount)
        remaining_amount -= penalty_paid

        # Deduct interest
        interest_paid = min(remaining_amount, monthly_interest)
        remaining_amount -= interest_paid

        # Remaining amount goes to principal
        principal_paid = min(remaining_amount, loan.balance_amount)
        
        # If payment exceeds what's needed, adjust principal to not exceed balance
        if principal_paid + interest_paid + penalty_paid > self.total_paid:
            # Recalculate to ensure exact match
            principal_paid = self.total_paid - interest_paid - penalty_paid

        self.penalty_amount = penalty_paid
        self.interest_amount = interest_paid
        self.principal_amount = principal_paid

        # Calculate new balance
        self.balance_after_payment = max(0, loan.balance_amount - self.principal_amount)
        
        # Ensure monetary values are rounded to 2 decimal places
        if self.penalty_amount:
            self.penalty_amount = round(float(self.penalty_amount), 2)
        if self.interest_amount:
            self.interest_amount = round(float(self.interest_amount), 2)
        if self.principal_amount:
            self.principal_amount = round(float(self.principal_amount), 2)
        if self.balance_after_payment:
            self.balance_after_payment = round(float(self.balance_after_payment), 2)

    def on_submit(self):
        """Update loan balance, GL, and schedule"""
        self.update_loan_balance()
        # ensure idempotent: if already posted -> skip
        if not self.get("posted_to_gl"):
            self.post_to_ledger()
        self.validate_gl_entries()
        self.update_member_totals()
        self.update_repayment_schedule()

    def validate_gl_entries(self):
        """Validate that GL entries were created properly"""
        if not self.journal_entry and not self.payment_entry:
            frappe.throw(_("Failed to create Journal Entry or Payment Entry for this loan repayment. Please check the system logs."))
            
        # Use validation utilities
        from shg.shg.utils.validation_utils import validate_reference_types_and_names, validate_custom_field_linking, validate_accounting_integrity
        validate_reference_types_and_names(self)
        validate_custom_field_linking(self)
        validate_accounting_integrity(self)

    def update_loan_balance(self):
        """Update the loan balance with improved accuracy"""
        loan = frappe.get_doc("SHG Loan", self.loan)
        
        # Update loan balance
        loan.balance_amount = max(0, loan.balance_amount - self.principal_amount)
        loan.last_repayment_date = self.repayment_date

        # Update next due date based on repayment frequency
        if loan.balance_amount > 0:
            if loan.repayment_frequency == "Daily":
                loan.next_due_date = add_days(getdate(self.repayment_date), 1)
            elif loan.repayment_frequency == "Weekly":
                loan.next_due_date = add_days(getdate(self.repayment_date), 7)
            elif loan.repayment_frequency == "Bi-Weekly":
                loan.next_due_date = add_days(getdate(self.repayment_date), 14)
            elif loan.repayment_frequency == "Monthly":
                loan.next_due_date = add_months(getdate(self.repayment_date), 1)
            elif loan.repayment_frequency == "Bi-Monthly":
                loan.next_due_date = add_months(getdate(self.repayment_date), 2)
            elif loan.repayment_frequency == "Quarterly":
                loan.next_due_date = add_months(getdate(self.repayment_date), 3)
            elif loan.repayment_frequency == "Yearly":
                loan.next_due_date = add_months(getdate(self.repayment_date), 12)
            else:
                # Default to monthly
                loan.next_due_date = add_months(getdate(self.repayment_date), 1)
        else:
            # Loan is fully paid
            loan.status = "Closed"
            loan.next_due_date = None

        loan.save()

    def post_to_ledger(self):
        """
        Create a Payment Entry for this loan repayment.
        """
        from shg.shg.utils.gl_utils import create_loan_repayment_payment_entry, update_document_with_payment_entry
        payment_entry = create_loan_repayment_payment_entry(self)
        update_document_with_payment_entry(self, payment_entry)

    def update_member_totals(self):
        """Update member's totals"""
        try:
            member_doc = frappe.get_doc("SHG Member", self.member)
            member_doc.update_financial_summary()
        except Exception as e:
            frappe.log_error(f"Failed to update member totals: {str(e)}")

    @frappe.whitelist()
    def send_payment_confirmation(self):
        """Send SMS confirmation"""
        try:
            member = frappe.get_doc("SHG Member", self.member)
            message = f"Payment received! Amount: {self.total_paid}, Principal: {self.principal_amount}, Interest: {self.interest_amount}"
            if self.penalty_amount > 0:
                message += f", Penalty: {self.penalty_amount}"
            message += f". Remaining balance: {self.balance_after_payment}."

            notification = frappe.get_doc({
                "doctype": "SHG Notification Log",
                "member": self.member,
                "notification_type": "Payment Receipt",
                "message": message,
                "channel": "SMS",
                "reference_document": self.doctype,
                "reference_name": self.name
            })
            notification.insert()

            from shg.tasks import send_sms
            if send_sms(member.phone_number, message):
                notification.status = "Sent"
                notification.sent_date = frappe.utils.now()
                notification.save()
            else:
                notification.status = "Failed"
                notification.error_message = "SMS sending failed"
                notification.save()

        except Exception as e:
            frappe.log_error(f"Failed to send payment confirmation: {str(e)}")

    def on_cancel(self):
        """Reverse repayment"""
        if self.journal_entry:
            try:
                je = frappe.get_doc("Journal Entry", self.journal_entry)
                if je.docstatus == 1:
                    je.cancel()
            except Exception as e:
                frappe.log_error(f"Failed to cancel journal entry: {str(e)}")
        elif self.payment_entry:
            try:
                pe = frappe.get_doc("Payment Entry", self.payment_entry)
                if pe.docstatus == 1:
                    pe.cancel()
            except Exception as e:
                frappe.log_error(f"Failed to cancel payment entry: {str(e)}")

        try:
            loan = frappe.get_doc("SHG Loan", self.loan)
            loan.balance_amount += self.principal_amount
            if loan.status == "Closed" and loan.balance_amount > 0:
                loan.status = "Disbursed"
                # Restore next due date based on repayment frequency
                if loan.repayment_frequency == "Daily":
                    loan.next_due_date = add_days(getdate(self.repayment_date), 1)
                elif loan.repayment_frequency == "Weekly":
                    loan.next_due_date = add_days(getdate(self.repayment_date), 7)
                elif loan.repayment_frequency == "Bi-Weekly":
                    loan.next_due_date = add_days(getdate(self.repayment_date), 14)
                elif loan.repayment_frequency == "Monthly":
                    loan.next_due_date = add_months(getdate(self.repayment_date), 1)
                elif loan.repayment_frequency == "Bi-Monthly":
                    loan.next_due_date = add_months(getdate(self.repayment_date), 2)
                elif loan.repayment_frequency == "Quarterly":
                    loan.next_due_date = add_months(getdate(self.repayment_date), 3)
                elif loan.repayment_frequency == "Yearly":
                    loan.next_due_date = add_months(getdate(self.repayment_date), 12)
                else:
                    # Default to monthly
                    loan.next_due_date = add_months(getdate(self.repayment_date), 1)
            loan.save()
            self.update_member_totals()
        except Exception as e:
            frappe.log_error(f"Failed to reverse loan balance: {str(e)}")

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

    def get_member_customer(self):
        """Get member's customer link"""
        member = frappe.get_doc("SHG Member", self.member)
        return member.customer

    def get_loan_account(self, company):
        """Get loan account from the associated loan"""
        if self.loan:
            loan = frappe.get_doc("SHG Loan", self.loan)
            return loan.get_loan_account(company)
        else:
            # Fallback to settings
            from shg.shg.utils.account_utils import get_or_create_shg_loans_account
            return get_or_create_shg_loans_account(company)

    def get_repayment_schedule_info(self):
        if self.loan:
            schedule_entry = frappe.db.get_value(
                "SHG Loan Repayment Schedule",
                {"loan": self.loan, "due_date": self.repayment_date, "status": "Pending"},
                ["principal_amount", "interest_amount", "total_amount"]
            )
            if schedule_entry:
                return {
                    "scheduled_principal": schedule_entry[0],
                    "scheduled_interest": schedule_entry[1],
                    "scheduled_total": schedule_entry[2]
                }
        return None

    def update_repayment_schedule(self):
        if self.loan:
            # Find the next pending repayment schedule entry
            schedule_entries = frappe.get_all(
                "SHG Loan Repayment Schedule",
                {"loan": self.loan, "status": "Pending"},
                ["name", "due_date"], 
                order_by="due_date"
            )
            
            if schedule_entries:
                # Update the earliest pending schedule entry
                schedule_doc = frappe.get_doc("SHG Loan Repayment Schedule", schedule_entries[0].name)
                schedule_doc.status = "Paid"
                schedule_doc.actual_payment_date = self.repayment_date
                schedule_doc.actual_amount_paid = self.total_paid
                schedule_doc.save()

                # If this payment was for a specific scheduled amount, check for over/under payment
                scheduled_info = self.get_repayment_schedule_info()
                if scheduled_info and scheduled_info["scheduled_total"]:
                    difference = self.total_paid - scheduled_info["scheduled_total"]
                    if abs(difference) > 1:  # More than KES 1 difference
                        # Log the difference for review
                        frappe.msgprint(
                            f"Payment amount differs from scheduled amount by KES {difference:,.2f}. "
                            "Please verify the payment allocation.",
                            alert=True
                        )


# --- Hook functions ---
# These are hook functions called from hooks.py and should NOT have @frappe.whitelist()
def validate_repayment(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()


def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    if doc.docstatus == 1 and not doc.get("posted_to_gl"):
        doc.post_to_ledger()