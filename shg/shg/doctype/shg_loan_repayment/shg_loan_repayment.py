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
        """Calculate principal, interest, and penalty breakdown"""
        if not self.loan:
            return
            
        loan = frappe.get_doc("SHG Loan", self.loan)

        # Calculate penalties
        if loan.next_due_date and getdate(self.repayment_date) > getdate(loan.next_due_date):
            overdue_days = (getdate(self.repayment_date) - getdate(loan.next_due_date)).days
            penalty_rate = 0.05  # 5% per month
            self.penalty_amount = loan.monthly_installment * penalty_rate * (overdue_days / 30)
        else:
            self.penalty_amount = 0

        remaining_amount = self.total_paid

        # Deduct penalty
        penalty_paid = min(remaining_amount, self.penalty_amount or 0)
        self.penalty_amount = penalty_paid
        remaining_amount -= penalty_paid

        # Interest
        monthly_interest = loan.balance_amount * (loan.interest_rate / 100) / 12
        interest_paid = min(remaining_amount, monthly_interest)
        self.interest_amount = interest_paid
        remaining_amount -= interest_paid

        # Principal
        self.principal_amount = remaining_amount

        # New balance
        self.balance_after_payment = max(0, loan.balance_amount - self.principal_amount)

    def on_submit(self):
        """Update loan balance, GL, and schedule"""
        self.update_loan_balance()
        self.create_journal_entry()
        self.update_member_totals()
        self.update_repayment_schedule()

    def update_loan_balance(self):
        """Update the loan balance"""
        loan = frappe.get_doc("SHG Loan", self.loan)
        loan.balance_amount = max(0, loan.balance_amount - self.principal_amount)
        loan.last_repayment_date = self.repayment_date

        if loan.balance_amount > 0:
            loan.next_due_date = add_months(getdate(self.repayment_date), 1)
        else:
            loan.status = "Closed"
            loan.next_due_date = None

        loan.save()

    def create_journal_entry(self):
        """Create Journal Entry for repayment"""
        company = frappe.defaults.get_user_default("Company")
        if not company:
            companies = frappe.get_all("Company", limit=1)
            if companies:
                company = companies[0].name
            else:
                frappe.throw(_("Please create a company first"))

        # Get configured accounts or use defaults
        settings = frappe.get_single("SHG Settings")
        bank_account = settings.default_bank_account if settings.default_bank_account else f"Bank - {company}"
        cash_account = settings.default_cash_account if settings.default_cash_account else f"Cash - {company}"
        
        # Get member's account (auto-created if not exists)
        member_account = self.get_member_account()
            
        # Determine which account to debit (bank or cash)
        debit_account = bank_account if frappe.db.exists("Account", bank_account) else cash_account

        # Get income accounts using the new utility functions
        from shg.shg.utils.account_utils import (
            get_or_create_shg_interest_income_account,
            get_or_create_shg_penalty_income_account
        )
        
        interest_income_account = get_or_create_shg_interest_income_account(company)
        penalty_income_account = get_or_create_shg_penalty_income_account(company)

        accounts = [
            {
                "account": debit_account,
                "debit_in_account_currency": self.total_paid,
                "reference_type": self.doctype,
                "reference_name": self.name
            },
            {
                "account": member_account,
                "credit_in_account_currency": self.principal_amount,
                "party_type": "Customer",
                "party": self.get_member_customer(),
                "reference_type": self.doctype,
                "reference_name": self.name
            }
        ]

        if self.interest_amount > 0:
            accounts.append({
                "account": interest_income_account,
                "credit_in_account_currency": self.interest_amount,
                "reference_type": self.doctype,
                "reference_name": self.name
            })

        if self.penalty_amount > 0:
            accounts.append({
                "account": penalty_income_account,
                "credit_in_account_currency": self.penalty_amount,
                "reference_type": self.doctype,
                "reference_name": self.name
            })

        je = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "posting_date": self.repayment_date,
            "company": company,
            "user_remark": f"Loan repayment from {self.member_name} - Principal: {self.principal_amount}, Interest: {self.interest_amount}, Penalty: {self.penalty_amount}",
            "accounts": accounts
        })

        try:
            je.insert()
            je.submit()
            self.journal_entry = je.name
            self.save()
            self.send_payment_confirmation()
        except Exception as e:
            frappe.log_error(f"Failed to post repayment to GL: {str(e)}")
            frappe.throw(f"Failed to post to General Ledger: {str(e)}")
            
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

    def update_member_totals(self):
        """Update member's totals"""
        try:
            member_doc = frappe.get_doc("SHG Member", self.member)
            member_doc.update_financial_summary()
        except Exception as e:
            frappe.log_error(f"Failed to update member totals: {str(e)}")

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

        try:
            loan = frappe.get_doc("SHG Loan", self.loan)
            loan.balance_amount += self.principal_amount
            if loan.status == "Closed" and loan.balance_amount > 0:
                loan.status = "Disbursed"
                loan.next_due_date = add_months(getdate(self.repayment_date), 1)
            loan.save()
            self.update_member_totals()
        except Exception as e:
            frappe.log_error(f"Failed to reverse loan balance: {str(e)}")

    # --------------------
    # 🔍 Extra Validations
    # --------------------

    def validate_repayment_amount(self):
        if self.total_paid <= 0:
            frappe.throw("Repayment amount must be greater than zero")

        if self.loan:
            loan = frappe.get_doc("SHG Loan", self.loan)
            monthly_interest = loan.balance_amount * (loan.interest_rate / 100) / 12
            max_penalty = loan.monthly_installment * 0.05 * 12
            max_payment = loan.balance_amount + monthly_interest + max_penalty

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
            schedule_entries = frappe.get_all(
                "SHG Loan Repayment Schedule",
                {"loan": self.loan, "status": "Pending"},
                ["name", "due_date"], order_by="due_date"
            )
            if schedule_entries:
                schedule_doc = frappe.get_doc("SHG Loan Repayment Schedule", schedule_entries[0].name)
                schedule_doc.status = "Paid"
                schedule_doc.actual_payment_date = self.repayment_date
                schedule_doc.actual_amount_paid = self.total_paid
                schedule_doc.save()