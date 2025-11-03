import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, add_months, flt, now_datetime, getdate, nowdate
from shg.shg.utils.account_helpers import get_or_create_member_receivable
from shg.shg.utils.schedule_math import generate_reducing_balance_schedule, generate_flat_rate_schedule

class SHGLoan(Document):
    """SHG Loan controller with automatic ledger and repayment schedule posting."""

    # ---------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------
    def validate(self):
        is_group_loan = bool(self.get("loan_members"))

        if not is_group_loan and not self.member:
            frappe.throw(_("Member is required for individual loans."))

        if not self.loan_amount or flt(self.loan_amount) <= 0:
            frappe.throw(_("Loan Amount must be greater than zero."))

        if self.interest_rate is None:
            frappe.throw(_("Interest Rate is required."))

        if not self.loan_period_months:
            frappe.throw(_("Loan Period (Months) is required."))

        if not getattr(self, "company", None):
            self.company = frappe.db.get_single_value("SHG Settings", "company")

        if is_group_loan:
            self.sync_group_allocations_total()

        self.run_eligibility_checks()
        self.calculate_repayment_details()

    # ---------------------------------------------------
    # GROUP LOAN LOGIC
    # ---------------------------------------------------
    def sync_group_allocations_total(self):
        """Ensure parent total = sum of allocations."""
        total = sum(flt(r.allocated_amount) for r in self.get("loan_members", []))
        self.loan_amount = total or 0

    def generate_individual_member_loans(self):
        """Split a group loan into individual member loans."""
        if not self.get("loan_members"):
            frappe.throw(_("No Loan Members found."))

        created = []
        for row in self.get("loan_members", []):
            if not row.member:
                continue
            if frappe.db.exists("SHG Loan", {"parent_loan": self.name, "member": row.member}):
                continue

            loan = frappe.new_doc("SHG Loan")
            loan.update({
                "loan_type": self.loan_type,
                "loan_amount": row.allocated_amount,
                "interest_rate": self.interest_rate,
                "interest_type": self.interest_type,
                "loan_period_months": self.loan_period_months,
                "repayment_frequency": self.repayment_frequency,
                "member": row.member,
                "member_name": row.member_name,
                "company": self.company,
                "repayment_start_date": self.repayment_start_date or today(),
                "status": "Approved",
                "parent_loan": self.name,
                "is_group_loan": 0
            })
            loan.insert(ignore_permissions=True)
            loan.create_repayment_schedule_if_needed()
            created.append(loan.name)

        frappe.db.commit()
        return created

    # ---------------------------------------------------
    # ELIGIBILITY
    # ---------------------------------------------------
    def run_eligibility_checks(self):
        settings = frappe.get_single("SHG Settings")
        min_savings = flt(getattr(settings, "min_savings_for_loan", 0))

        def _check(member_id):
            m = frappe.get_doc("SHG Member", member_id)
            if getattr(m, "membership_status", "Active") != "Active":
                frappe.throw(_("{0} is not Active.").format(m.member_name))
            if min_savings and flt(m.total_contributions or 0) < min_savings:
                frappe.throw(_("{0} has not met minimum savings.").format(m.member_name))

        if self.get("loan_members"):
            for r in self.loan_members:
                if r.member:
                    _check(r.member)
        elif self.member:
            _check(self.member)

    # ---------------------------------------------------
    # REPAYMENT CALCULATIONS
    # ---------------------------------------------------
    def calculate_repayment_details(self):
        """Compute installment and total payable."""
        if not self.loan_amount or not self.interest_rate or not self.loan_period_months:
            return
            
        if self.interest_type == "Flat Rate":
            calc = self.calculate_flat_interest()
            self.monthly_installment = calc["monthly_installment"]
            self.total_payable = calc["total_amount"]
            self.total_interest_payable = calc["total_interest"]
        else:
            emi = self.calculate_emi()
            self.monthly_installment = emi
            self.total_payable = emi * self.loan_period_months
            # Calculate total interest for reducing balance
            self.total_interest_payable = self.total_payable - self.loan_amount

    def calculate_emi(self):
        """Calculate EMI for reducing balance loans."""
        principal = flt(self.loan_amount)
        annual_rate = flt(self.interest_rate)
        months = int(self.loan_period_months)
        
        if months <= 0:
            return 0
            
        # Monthly interest rate
        monthly_rate = annual_rate / 100.0 / 12.0
        
        # If interest rate is 0, simple division
        if monthly_rate == 0:
            return principal / months
            
        # EMI formula: P * r * (1 + r)^n / ((1 + r)^n - 1)
        emi = principal * monthly_rate * ((1 + monthly_rate) ** months) / (((1 + monthly_rate) ** months) - 1)
        return emi

    def calculate_flat_interest(self):
        """Calculate total interest for flat rate loans."""
        principal = flt(self.loan_amount)
        annual_rate = flt(self.interest_rate)
        months = int(self.loan_period_months)
        
        # Total interest = Principal * Rate * Time
        total_interest = principal * (annual_rate / 100.0) * (months / 12.0)
        total_amount = principal + total_interest
        monthly_installment = total_amount / months if months > 0 else 0
        monthly_interest = total_interest / months if months > 0 else 0
        
        return {
            "total_interest": total_interest,
            "monthly_interest": monthly_interest,
            "total_amount": total_amount,
            "monthly_installment": monthly_installment
        }

    # ---------------------------------------------------
    # POST TO LEDGER
    # ---------------------------------------------------
    def post_to_ledger_if_needed(self):
        """Create Journal Entry for loan disbursement."""
        if getattr(self, "posted_to_gl", 0):
            return

        # Ensure company is set with fallback logic
        company = self.company or frappe.db.get_single_value("SHG Settings", "company")
        if not company:
            frappe.throw(_("Company not set on loan or in SHG Settings."))

        abbr = frappe.db.get_value("Company", company, "abbr")
        settings = frappe.get_single("SHG Settings")
        loan_source_account = getattr(settings, "default_loan_account", None)
        if not loan_source_account:
            frappe.throw(_("Please set Default Loan Account in SHG Settings."))

        is_group = bool(self.get("loan_members"))
        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.company = company
        je.posting_date = self.disbursement_date or today()
        je.user_remark = f"Loan disbursement for {self.name}"

        if is_group:
            for r in self.get("loan_members", []):
                if not r.member or not flt(r.allocated_amount):
                    continue
                member_account = get_or_create_member_receivable(r.member, company)
                cust = frappe.db.get_value("SHG Member", r.member, "customer") or r.member
                je.append("accounts", {
                    "account": member_account,  # 👈 must be the member subaccount
                    "party_type": "Customer",
                    "party": cust,
                    "debit_in_account_currency": flt(r.allocated_amount),
                    "company": company
                })
        else:
            member_account = get_or_create_member_receivable(self.member, company)
            cust = frappe.db.get_value("SHG Member", self.member, "customer") or self.member
            je.append("accounts", {
                "account": member_account,  # 👈 must be the member subaccount
                "party_type": "Customer",
                "party": cust,
                "debit_in_account_currency": flt(self.loan_amount),
                "company": company
            })

        total = sum(flt(r.allocated_amount) for r in self.get("loan_members", [])) if is_group else flt(self.loan_amount)
        main_member = self.member if not is_group else self.loan_members[0].member
        cust = frappe.db.get_value("SHG Member", main_member, "customer") or main_member

        je.append("accounts", {
            "account": loan_source_account,
            "credit_in_account_currency": total,
            "company": company,
            "party_type": "Customer",
            "party": cust,
            "is_advance": "No"
        })

        try:
            je.insert(ignore_permissions=True)
            je.submit()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Loan JE Post Error")
            frappe.throw(_("Failed to post Journal Entry: {0}").format(e))

        self.db_set("journal_entry", je.name)
        self.db_set("posted_to_gl", 1)
        self.db_set("status", "Disbursed")
        frappe.msgprint(f"✅ Loan {self.name} posted as {je.name}")

    # ---------------------------------------------------
    # REPAYMENT SCHEDULE
    # ---------------------------------------------------
    def create_repayment_schedule_if_needed(self):
        """Auto-generate repayment schedule on creation/disbursement."""
        if self.get("repayment_schedule"):
            return

        principal = flt(self.loan_amount)
        months = int(self.loan_period_months)
        start = self.repayment_start_date or add_months(self.disbursement_date or today(), 1)
        interest_type = getattr(self, "interest_type", "Reducing Balance")

        if interest_type == "Flat Rate":
            schedule = generate_flat_rate_schedule(principal, self.interest_rate, months, start)
        else:
            schedule = generate_reducing_balance_schedule(principal, self.interest_rate, months, start)

        # Add schedule rows to loan
        for row_data in schedule:
            self.append("repayment_schedule", row_data)

        frappe.msgprint(_("✅ Repayment schedule created with {0} installments.").format(len(schedule)))

    @frappe.whitelist()
    def mark_all_due_as_paid(self):
        """Mark all due installments as paid"""
        if not self.get("repayment_schedule"):
            return
            
        today_date = getdate(nowdate())
        updated_count = 0
        
        for row in self.get("repayment_schedule"):
            # Check if the installment is due (not paid and due date is today or past)
            due_date = getdate(row.due_date) if row.due_date else today_date
            if row.status in ["Pending", "Overdue"] and due_date <= today_date and flt(row.unpaid_balance) > 0:
                # Mark as paid using the existing method
                try:
                    schedule_doc = frappe.get_doc("SHG Loan Repayment Schedule", row.name)
                    schedule_doc.mark_as_paid(row.unpaid_balance)
                    updated_count += 1
                except Exception as e:
                    frappe.log_error(frappe.get_traceback(), f"Failed to mark installment {row.name} as paid")
                    
        if updated_count > 0:
            frappe.msgprint(_(f"✅ {updated_count} installments marked as paid."))
            self.reload()
        else:
            frappe.msgprint(_("No due installments found to mark as paid."))

    def update_repayment_summary(self):
        """Refresh repayment summary fields from repayment schedule."""
        # Allow updates on submitted loans
        self.flags.ignore_validate_update_after_submit = True
        
        # Compute repayment summary
        summary = self.compute_repayment_summary()
        
        # Update loan fields with computed values
        self.total_repaid = flt(summary["total_repaid"], 2)
        self.balance_amount = flt(summary["balance_amount"], 2)
        self.overdue_amount = flt(summary["overdue_amount"], 2)
        self.next_due_date = summary["next_due_date"]
        self.last_repayment_date = summary["last_repayment_date"]
        self.monthly_installment = flt(summary["monthly_installment"], 2)
        
        # Save the document
        self.save(ignore_permissions=True)

    def compute_repayment_summary(self):
        """Compute repayment summary from repayment schedule child table.
        
        Returns:
            dict: Summary with total_repaid, balance_amount, overdue_amount, etc.
        """
        # Get schedule from child table
        schedule = self.get("repayment_schedule") or frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={"parent": self.name},
            fields=["total_payment", "amount_paid", "unpaid_balance", "status", "due_date", "actual_payment_date"]
        )

        # Calculate totals from schedule
        total_payable = sum(flt(r.get("total_payment")) for r in schedule)
        total_repaid = sum(flt(r.get("amount_paid")) for r in schedule)
        balance = sum(flt(r.get("unpaid_balance")) for r in schedule)
        
        # Calculate overdue amount
        overdue_amount = 0
        today_date = getdate(nowdate())
        for r in schedule:
            due_date = getdate(r.get("due_date")) if r.get("due_date") else today_date
            # Overdue if not paid and due date is in the past
            if r.get("status") != "Paid" and due_date < today_date and flt(r.get("unpaid_balance")) > 0:
                overdue_amount += flt(r.get("unpaid_balance"))

        # Calculate next due date (first pending/overdue installment)
        next_due_date = None
        # Sort schedule by due date
        sorted_schedule = sorted(schedule, key=lambda x: x.get("due_date") or frappe.utils.getdate())
        # Find next due date
        for r in sorted_schedule:
            if r.get("status") in ["Pending", "Overdue"] and flt(r.get("unpaid_balance")) > 0:
                next_due_date = r.get("due_date")
                break

        # Find last repayment date (latest paid installment)
        last_repayment_date = None
        paid_schedule = [r for r in sorted_schedule if r.get("status") == "Paid"]
        if paid_schedule:
            # Find the latest actual_payment_date among paid installments
            for r in paid_schedule:
                # Use a safer approach instead of hasattr for Server Script compatibility
                try:
                    # Try to get the attribute - if it doesn't exist, this will raise an AttributeError
                    actual_payment_date = r.actual_payment_date
                    has_actual_payment_date = True
                except AttributeError:
                    has_actual_payment_date = False
                    actual_payment_date = None
                
                if has_actual_payment_date and actual_payment_date:
                    payment_date = getdate(actual_payment_date)
                    if not last_repayment_date or payment_date > last_repayment_date:
                        last_repayment_date = payment_date

        # Set monthly installment from first schedule row if available
        monthly_installment = 0
        if sorted_schedule:
            monthly_installment = flt(sorted_schedule[0].get("total_payment"))

        return {
            "total_payable": flt(total_payable, 2),
            "total_repaid": flt(total_repaid, 2),
            "balance_amount": flt(balance, 2),
            "overdue_amount": flt(overdue_amount, 2),
            "next_due_date": next_due_date,
            "last_repayment_date": last_repayment_date,
            "monthly_installment": flt(monthly_installment, 2)
        }

@frappe.whitelist()
def refresh_repayment_summary(loan_name):
    """Recalculate repayment summary from schedule and update loan fields."""
    from shg.shg.api.loan import refresh_repayment_summary as api_refresh_summary
    return api_refresh_summary(loan_name)


@frappe.whitelist()
def update_repayment_summary(loan_id):
    """Refresh repayment summary fields from repayment schedule."""
    if not loan_id:
        frappe.throw("Loan ID is required.")
        
    loan = frappe.get_doc("SHG Loan", loan_id)
    loan.update_repayment_summary()
    return True


@frappe.whitelist()
def get_member_loan_statement(loan_id=None, member=None):
    """
    Returns loan + repayment schedule for a given member or loan_id.
    Either argument is accepted.
    """
    from shg.shg.api.loan import get_member_loan_statement as api_get_statement
    return api_get_statement(loan_name=loan_id, member=member)


def before_save(doc, method=None):
    """Hook to safely round and validate before saving."""
    for field in ["loan_amount", "monthly_installment", "total_payable", "balance_amount"]:
        if getattr(doc, field, None):
            setattr(doc, field, round(flt(getattr(doc, field)), 2))
    doc.calculate_repayment_details()

def check_member_eligibility(doc):
    """Ensure member is active and eligible."""
    if not doc.member:
        frappe.throw("Member is required.")
    if not frappe.db.exists("SHG Member", doc.member):
        frappe.throw(f"Member {doc.member} does not exist.")
    member_status = frappe.db.get_value("SHG Member", doc.member, "membership_status")
    if member_status != "Active":
        frappe.throw(f"Member {doc.member} is not active.")

def validate_loan(doc, method=None):
    doc.validate()

def post_to_general_ledger(doc, method=None):
    if doc.docstatus == 1 and not doc.get("posted_to_gl"):
        doc.post_to_ledger_if_needed()

def after_insert_or_update(doc, method=None):
    """Auto actions after saving loan."""
    if doc.get("loan_members"):
        doc.generate_individual_member_loans()
    else:
        doc.create_repayment_schedule_if_needed()

def on_submit(doc, method=None):
    """Post to ledger and create schedule on submit."""
    doc.post_to_ledger_if_needed()
    doc.create_repayment_schedule_if_needed()
    doc.db_set("status", "Disbursed")
    doc.db_set("disbursed_on", now_datetime())
    frappe.msgprint(_(f"Loan {doc.name} successfully disbursed and schedule created."))
