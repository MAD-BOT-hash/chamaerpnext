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
            
        # Verify the journal entry or payment entry exists and is submitted
        try:
            if self.journal_entry:
                je = frappe.get_doc("Journal Entry", self.journal_entry)
                if je.docstatus != 1:
                    frappe.throw(_("Journal Entry was not submitted successfully."))
                    
                # Verify accounts and amounts
                if len(je.accounts) < 2:
                    frappe.throw(_("Journal Entry should have at least 2 accounts."))
                    
                total_debit = sum(entry.debit_in_account_currency for entry in je.accounts)
                total_credit = sum(entry.credit_in_account_currency for entry in je.accounts)
                    
                if abs(total_debit - total_credit) > 0.01:
                    frappe.throw(_("Total debit and credit amounts must be equal."))
                    
                # Verify party details for credit entry
                credit_entry_with_party = None
                for entry in je.accounts:
                    if entry.credit_in_account_currency > 0 and entry.party_type and entry.party:
                        credit_entry_with_party = entry
                        break
                        
                if credit_entry_with_party and credit_entry_with_party.party_type != "Customer":
                    frappe.throw(_("Credit entry party type must be 'Customer'."))
            elif self.payment_entry:
                pe = frappe.get_doc("Payment Entry", self.payment_entry)
                if pe.docstatus != 1:
                    frappe.throw(_("Payment Entry was not submitted successfully."))
                    
                # Verify payment entry details
                if pe.payment_type != "Receive":
                    frappe.throw(_("Payment Entry must be of type 'Receive' for loan repayments."))
                    
                if not pe.party_type or not pe.party:
                    frappe.throw(_("Payment Entry must have party type and party set."))
                    
                if pe.party_type != "Customer":
                    frappe.throw(_("Payment Entry party type must be 'Customer'."))
                    
                if abs(pe.paid_amount - self.total_paid) > 0.01:
                    frappe.throw(_("Payment Entry amount does not match repayment amount."))
                
        except frappe.DoesNotExistError:
            if self.journal_entry:
                frappe.throw(_("Journal Entry {0} does not exist.").format(self.journal_entry))
            elif self.payment_entry:
                frappe.throw(_("Payment Entry {0} does not exist.").format(self.payment_entry))
        except Exception as e:
            frappe.throw(_("Error validating GL Entry: {0}").format(str(e)))

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

    def post_to_ledger(self):
        """
        Create a Payment Entry or Journal Entry for this loan repayment.
        Use SHG Settings to decide; default to Journal Entry.
        """
        settings = frappe.get_single("SHG Settings")
        posting_method = getattr(settings, "loan_repayment_posting_method", "Journal Entry")

        # Prepare common data
        company = frappe.get_value("Global Defaults", None, "default_company") or settings.company
        member_customer = frappe.get_value("SHG Member", self.member, "customer")

        # Choose posting
        if posting_method == "Payment Entry":
            pe = self._create_payment_entry(member_customer, company)
            self.payment_entry = pe.name
        else:
            je = self._create_journal_entry(member_customer, company)
            self.journal_entry = je.name

        self.posted_to_gl = 1
        self.posted_on = frappe.utils.now()
        self.save()
        
    def _create_journal_entry(self, party_customer, company):
        from frappe.utils import flt, today
        
        # Get member's account (auto-created if not exists)
        member_account = self.get_member_account()
            
        # Get income accounts using the new utility functions
        from shg.shg.utils.account_utils import (
            get_or_create_shg_interest_income_account,
            get_or_create_shg_penalty_income_account
        )
        
        interest_income_account = get_or_create_shg_interest_income_account(company)
        penalty_income_account = get_or_create_shg_penalty_income_account(company)

        accounts = [
            {
                "account": self.get_cash_account(company),
                "debit_in_account_currency": flt(self.total_paid),
                "reference_type": "Journal Entry",
                "reference_name": self.name
            },
            {
                "account": member_account,
                "credit_in_account_currency": flt(self.principal_amount),
                "party_type": "Customer",
                "party": party_customer,
                "reference_type": "Journal Entry",
                "reference_name": self.name
            }
        ]

        if self.interest_amount > 0:
            accounts.append({
                "account": interest_income_account,
                "credit_in_account_currency": flt(self.interest_amount),
                "reference_type": "Journal Entry",
                "reference_name": self.name
            })

        if self.penalty_amount > 0:
            accounts.append({
                "account": penalty_income_account,
                "credit_in_account_currency": flt(self.penalty_amount),
                "reference_type": "Journal Entry",
                "reference_name": self.name
            })

        je = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "posting_date": self.repayment_date or today(),
            "company": company,
            "user_remark": f"SHG Loan Repayment {self.name} from {self.member_name} - Principal: {self.principal_amount}, Interest: {self.interest_amount}, Penalty: {self.penalty_amount}",
            "accounts": accounts
        })

        je.insert(ignore_permissions=True)
        je.submit()
        return je
        
    def _create_payment_entry(self, party_customer, company):
        # create Payment Entry (Receive)
        from frappe.utils import flt, today
        pe = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "posting_date": self.repayment_date or today(),
            "company": company,
            "party_type": "Customer",
            "party": party_customer,
            "paid_from": self.get_cash_account(company),
            "paid_to": self.get_member_account(),
            "paid_amount": flt(self.total_paid),
            "received_amount": flt(self.total_paid),
            "reference_no": self.name,
            "reference_date": self.repayment_date or today()
        })
        pe.insert(ignore_permissions=True)
        pe.submit()
        return pe
        
    def get_cash_account(self, company):
        """Get cash or bank account from settings or defaults"""
        settings = frappe.get_single("SHG Settings")
        if settings.default_bank_account:
            return settings.default_bank_account
        elif settings.default_cash_account:
            return settings.default_cash_account
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
                # Try cash account
                cash_accounts = frappe.get_all("Account", filters={
                    "company": company,
                    "account_type": "Cash",
                    "is_group": 0
                }, limit=1)
                if cash_accounts:
                    return cash_accounts[0].name
                else:
                    frappe.throw(_("Please configure default bank or cash account in SHG Settings"))
            
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