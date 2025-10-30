import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, add_months, flt, now_datetime

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

        company = self.company
        abbr = frappe.db.get_value("Company", company, "abbr")
        settings = frappe.get_single("SHG Settings")
        loan_source_account = getattr(settings, "default_loan_account", None)
        if not loan_source_account:
            frappe.throw(_("Please set Default Loan Account in SHG Settings."))

        # Parent loan receivable
        def ensure_parent_account():
            parent = f"SHG Loans receivable - {abbr}"
            if not frappe.db.exists("Account", parent):
                ar = f"Accounts Receivable - {abbr}"
                if not frappe.db.exists("Account", ar):
                    frappe.throw(_("{0} not found").format(ar))
                frappe.get_doc({
                    "doctype": "Account",
                    "account_name": "SHG Loans receivable",
                    "name": parent,
                    "parent_account": ar,
                    "company": company,
                    "is_group": 1,
                    "account_type": "Receivable"
                }).insert(ignore_permissions=True)
                frappe.db.commit()
            else:
                frappe.db.set_value("Account", parent, "is_group", 1)
            return parent

        def ensure_member_account(member_id):
            parent = ensure_parent_account()
            acc_name = f"{member_id} - {abbr}"
            if not frappe.db.exists("Account", acc_name):
                member_name = frappe.db.get_value("SHG Member", member_id, "member_name") or member_id
                frappe.get_doc({
                    "doctype": "Account",
                    "account_name": member_name,
                    "name": acc_name,
                    "parent_account": parent,
                    "company": company,
                    "is_group": 0,
                    "account_type": "Receivable"
                }).insert(ignore_permissions=True)
                frappe.db.commit()
            return acc_name

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
                acc = ensure_member_account(r.member)
                cust = frappe.db.get_value("SHG Member", r.member, "customer") or r.member
                je.append("accounts", {
                    "account": acc,
                    "party_type": "Customer",
                    "party": cust,
                    "debit_in_account_currency": flt(r.allocated_amount),
                    "company": company
                })
        else:
            acc = ensure_member_account(self.member)
            cust = frappe.db.get_value("SHG Member", self.member, "customer") or self.member
            je.append("accounts", {
                "account": acc,
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

    def before_save(self):
        """Ensure total loan amount = sum of allocations before save."""
        is_group_loan = bool(self.get("loan_members"))
        if is_group_loan and getattr(self, "loan_members", None):
            total = sum(flt(r.allocated_amount) for r in self.loan_members)
            self.loan_amount = total or 0

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
# -------------------------------
# HOOKS
# -------------------------------
def validate_loan(doc, method):
    doc.validate()

def post_to_general_ledger(doc, method):
    if doc.docstatus == 1 and not doc.get("posted_to_gl"):
        doc.post_to_ledger_if_needed()

def after_insert_or_update(doc):
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