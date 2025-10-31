import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, add_months, flt, now_datetime, getdate, nowdate
from shg.shg.utils.account_helpers import get_or_create_member_receivable

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
            "party": cust
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
            self._generate_flat_rate_schedule(principal, months, start)
        else:
            self._generate_reducing_balance_schedule(principal, months, start)

        frappe.msgprint(_("✅ Repayment schedule created with {0} installments.").format(months))

    def _generate_flat_rate_schedule(self, principal, months, start):
        rate = flt(self.interest_rate)
        total_interest = principal * (rate / 100) * (months / 12)
        total = principal + total_interest
        monthly = total / months
        principal_part = principal / months
        interest_part = monthly - principal_part
        outstanding = principal
        date = start

        for i in range(1, months + 1):
            outstanding -= principal_part
            self.append("repayment_schedule", {
                "installment_no": i,
                "due_date": date,
                "principal_component": round(principal_part, 2),
                "interest_component": round(interest_part, 2),
                "total_payment": round(monthly, 2),
                "loan_balance": round(outstanding, 2),
                "status": "Pending"
            })
            date = add_months(date, 1)
        self.db_set("balance_amount", round(principal, 2))

    def _generate_reducing_balance_schedule(self, principal, months, start):
        r = flt(self.interest_rate) / 100.0 / 12.0
        emi = principal * r * ((1 + r) ** months) / (((1 + r) ** months) - 1) if r else principal / months
        outstanding = principal
        date = start

        for i in range(1, months + 1):
            interest = outstanding * r
            principal_part = emi - interest
            outstanding -= principal_part
            self.append("repayment_schedule", {
                "installment_no": i,
                "due_date": date,
                "principal_component": round(principal_part, 2),
                "interest_component": round(interest, 2),
                "total_payment": round(emi, 2),
                "loan_balance": round(outstanding, 2),
                "status": "Pending"
            })
            date = add_months(date, 1)
        self.db_set("balance_amount", round(principal, 2))

    @frappe.whitelist()
    def get_member_loan_statement(self):
        """
        Generate a loan statement for a member.
        Returns loan details and repayment schedule.
        """
        statement = {
            "loan_details": {
                "loan_id": self.name,
                "member_name": self.member_name,
                "loan_amount": self.loan_amount,
                "interest_rate": self.interest_rate,
                "interest_type": self.interest_type,
                "loan_period_months": self.loan_period_months,
                "disbursement_date": self.disbursement_date,
                "status": self.status,
                "balance_amount": self.balance_amount,
                "total_repaid": self.total_repaid
            },
            "repayment_schedule": [],
            "summary": {
                "total_due": 0,
                "total_paid": 0,
                "outstanding_balance": 0,
                "overdue_count": 0
            }
        }
        
        # Add repayment schedule details
        total_due = 0
        total_paid = 0
        overdue_count = 0
        
        for row in self.get("repayment_schedule", []):
            installment = {
                "installment_no": row.installment_no,
                "due_date": row.due_date,
                "total_due": row.total_due,
                "amount_paid": row.amount_paid,
                "unpaid_balance": row.unpaid_balance,
                "status": row.status
            }
            statement["repayment_schedule"].append(installment)
            
            total_due += flt(row.total_due)
            total_paid += flt(row.amount_paid)
            
            if row.status == "Overdue":
                overdue_count += 1
        
        # Update summary
        statement["summary"]["total_due"] = total_due
        statement["summary"]["total_paid"] = total_paid
        statement["summary"]["outstanding_balance"] = total_due - total_paid
        statement["summary"]["overdue_count"] = overdue_count
        
        return statement

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

# -------------------------------
@frappe.whitelist()
def get_member_loan_statement(member):
    """
    Returns a detailed loan statement for a specific member,
    including repayment schedule details and balances.
    """
    if not member:
        frappe.throw(_("Member is required."))

    # Validate member existence
    if not frappe.db.exists("SHG Member", member):
        frappe.throw(_("Member {0} not found.").format(member))

    # Fetch all active or closed loans for this member
    loans = frappe.get_all(
        "SHG Loan",
        filters={"member": member},
        fields=["name", "loan_amount", "interest_rate", "status", "repayment_start_date"],
        order_by="repayment_start_date desc"
    )

    if not loans:
        return {"member": member, "loans": [], "total_outstanding": 0}

    statement = []
    total_outstanding = 0

    for loan in loans:
        # Get repayment schedule
        schedule_rows = frappe.get_all(
            "SHG Loan Repayment Schedule",
            filters={"parent": loan.name},
            fields=[
                "due_date",
                "principal_amount",
                "interest_amount",
                "total_payment",
                "amount_paid",
                "unpaid_balance",
                "status"
            ],
            order_by="due_date asc"
        )

        principal_due = sum(flt(r["principal_amount"]) for r in schedule_rows)
        principal_paid = sum(flt(r["amount_paid"]) for r in schedule_rows)
        total_due = sum(flt(r["total_payment"]) for r in schedule_rows)
        balance = principal_due - principal_paid

        total_outstanding += balance

        statement.append({
            "loan_id": loan.name,
            "loan_amount": flt(loan.loan_amount),
            "interest_rate": flt(loan.interest_rate),
            "status": loan.status,
            "repayment_start_date": loan.repayment_start_date,
            "total_due": total_due,
            "total_paid": principal_paid,
            "balance": balance,
            "schedule": schedule_rows
        })

    return {
        "member": member,
        "loans": statement,
        "total_outstanding": round(total_outstanding, 2)
    }

def before_save(doc, method=None):
    """Hook to safely round and validate before saving."""
    for field in ["loan_amount", "monthly_installment", "total_payable", "balance_amount"]:
        if getattr(doc, field, None):
            setattr(doc, field, round(flt(getattr(doc, field)), 2))
    if hasattr(doc, "calculate_repayment_details"):
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

def calculate_repayment_details(doc):
    """Compute installment and total payable."""
    if not doc.loan_amount or not doc.interest_rate or not doc.loan_period_months:
        return
    monthly_rate = (doc.interest_rate / 100) / 12
    if monthly_rate and doc.loan_period_months:
        doc.monthly_installment = (
            doc.loan_amount * monthly_rate *
            (1 + monthly_rate) ** doc.loan_period_months
        ) / ((1 + monthly_rate) ** doc.loan_period_months - 1)
    doc.total_payable = doc.monthly_installment * doc.loan_period_months

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
