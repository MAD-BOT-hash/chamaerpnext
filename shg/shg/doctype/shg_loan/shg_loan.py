import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
    today,
    add_months,
    flt,
    now_datetime,
    getdate,
)

class SHGLoan(Document):
    """
    SHG Loan controller:
    - Supports both group loans and individual member loans
    - Handles disbursement posting to GL
    - Auto-generates repayment schedule
    - Tracks outstanding balance / status
    """

    # --------------------------
    # VALIDATION & LIFECYCLE
    # --------------------------
    def validate(self):
        """
        Validate core loan data before saving.
        """

        # Determine if this is a group loan based on presence of loan_members
        is_group_loan = bool(self.get("loan_members"))

        # Required fields
        if not is_group_loan:
            # Individual loan must have a member
            if not self.member:
                frappe.throw(_("Member is required for individual loans."))

        if not self.loan_amount or flt(self.loan_amount) <= 0:
            frappe.throw(_("Loan Amount must be greater than zero."))

        if not self.interest_rate and self.interest_rate != 0:
            frappe.throw(_("Interest Rate is required."))

        if not self.loan_period_months:
            frappe.throw(_("Loan Period (Months) is required."))

        # Auto-fetch company from SHG Settings if not set
        if not self.company:
            self.company = frappe.db.get_single_value("SHG Settings", "default_company")

        # If this is a group loan, force total = sum of allocations
        if is_group_loan:
            self.sync_group_allocations_total()

        # Check eligibility for each member (group loan) or the single loan member
        self.run_eligibility_checks()

    def on_submit(self):
        """
        On submit we treat this as 'DISBURSED' for individual loans.
        Group loans are typically NOT submitted (only approved).
        """
        # Determine if this is a group loan based on presence of loan_members
        is_group_loan = bool(self.get("loan_members"))

        # Prevent accidental submission of a group container loan
        if is_group_loan:
            frappe.throw(_("Group Loan cannot be submitted. Generate individual member loans first."))

        # 1. Post disbursement to ledger if not already posted
        self.post_to_ledger_if_needed()

        # 2. Create repayment schedule (idempotent)
        self.create_repayment_schedule_if_needed()

        # 3. Mark status
        self.db_set("status", "Disbursed")
        self.db_set("disbursed_on", now_datetime())

        frappe.msgprint(_("Loan {0} successfully disbursed, GL posted and repayment schedule created.").format(self.name))

    # --------------------------
    # GROUP LOAN LOGIC
    # --------------------------
    def sync_group_allocations_total(self):
        """
        Ensure total loan_amount = sum of allocated_amount in child table.
        Mirrors your before_save() logic.
        """
        total_allocated = 0
        for row in self.get("loan_members", []):
            total_allocated += flt(row.allocated_amount)

        # Force parent total to match allocations
        self.loan_amount = total_allocated or 0

    def generate_individual_member_loans(self):
        """
        Split a group loan into individual SHG Loan docs (one per member).
        Mirrors and improves your generate_individual_loans().

        Returns list of created loan names.
        """
        # Determine if this is a group loan based on presence of loan_members
        is_group_loan = bool(self.get("loan_members"))

        if not is_group_loan:
            frappe.throw(_("This is not a group loan."))

        created = []
        for m in self.get("loan_members", []):
            if not m.member:
                frappe.msgprint(_("Skipping a row with no member."), alert=True)
                continue

            # Avoid duplicates if already generated
            existing = frappe.db.exists(
                "SHG Loan",
                {
                    "parent_loan": self.name,
                    "member": m.member,
                    "docstatus": ["<", 2],  # draft/submit
                }
            )
            if existing:
                continue

            new_loan = frappe.new_doc("SHG Loan")
            new_loan.update({
                "loan_type": self.loan_type,
                "loan_amount": m.allocated_amount,
                "interest_rate": self.interest_rate,
                "interest_type": getattr(self, "interest_type", None),
                "loan_period_months": self.loan_period_months,
                "repayment_frequency": getattr(self, "repayment_frequency", "Monthly"),
                "member": m.member,
                "member_name": m.member_name,
                "company": self.company,
                "repayment_start_date": self.repayment_start_date or today(),
                "status": "Approved",
                "parent_loan": self.name,
                "is_group_loan": 0
            })
            new_loan.insert(ignore_permissions=True)

            created.append(new_loan.name)

        frappe.db.commit()
        return created

    # --------------------------
    # ELIGIBILITY
    # --------------------------
    def run_eligibility_checks(self):
        """
        Run chama rules like:
        - Member must be Active
        - Member must not be in arrears beyond threshold
        - Member must have minimum savings, etc.
        If it's a group loan, check each listed member.
        """
        settings = frappe.get_single("SHG Settings")

        # Sample policy values we expect to exist in SHG Settings:
        min_savings = flt(getattr(settings, "min_savings_for_loan", 0))
        max_arrears_days = getattr(settings, "max_arrears_days", 30)

        def _check(member_id):
            member_doc = frappe.get_doc("SHG Member", member_id)

            # 1. membership_status must be Active
            if getattr(member_doc, "membership_status", "Active") != "Active":
                frappe.throw(_("{0} is not Active and cannot receive a loan.").format(member_doc.member_name))

            # 2. savings threshold check (we assume member_doc.total_contributions is cumulative savings)
            if min_savings and flt(member_doc.total_contributions or 0) < min_savings:
                frappe.throw(_("{0} has not met the minimum savings requirement.").format(member_doc.member_name))

            # 3. arrears check (pseudo: you can refine with actual overdue schedule queries)
            # Future improvement: query SHG Loan Repayment Schedule for unpaid where due_date < today()-max_arrears_days

        # Determine if this is a group loan based on presence of loan_members
        is_group_loan = bool(self.get("loan_members"))

        if is_group_loan:
            for row in self.get("loan_members", []):
                if row.member:
                    _check(row.member)
        else:
            if self.member:
                _check(self.member)

    # --------------------------
    # LEDGER POSTING
    # --------------------------
    def post_to_ledger_if_needed(self):
        """
        Create GL entries for the disbursed loan if not already posted.
        Your original method was post_to_ledger() with manual GL Entry rows.
        We keep the same accounting logic, but make it idempotent and safer.
        """

        if getattr(self, "posted_to_gl", 0):
            return

        company = self.company or frappe.db.get_single_value("SHG Settings", "default_company")
        if not company:
            frappe.throw(_("Please set Default Company in SHG Settings."))

        # Get accounts from SHG Settings
        settings = frappe.get_single("SHG Settings")
        loan_source_account = settings.default_loan_account
        receivable_account = settings.member_receivable_account

        if not loan_source_account or not receivable_account:
            frappe.throw(_("Please set Default Loan and Receivable Accounts in SHG Settings."))

        posting_date = self.disbursement_date or today()

        # Create two GL Entry docs like you already do
        entries = [
            # Debit: member receivable (we gave them money)
            dict(
                account=receivable_account,
                party_type="Customer",
                party=self.member,
                debit=self.loan_amount,
                credit=0,
                voucher_type="SHG Loan",
                voucher_no=self.name,
                company=company,
                posting_date=posting_date,
                remarks=f"Loan disbursement for {self.member}",
            ),
            # Credit: loan source pool / cash
            dict(
                account=loan_source_account,
                debit=0,
                credit=self.loan_amount,
                voucher_type="SHG Loan",
                voucher_no=self.name,
                company=company,
                posting_date=posting_date,
                remarks=f"Loan disbursement for {self.member}",
            ),
        ]

        for e in entries:
            gl = frappe.new_doc("GL Entry")
            for k, v in e.items():
                setattr(gl, k, v)
            gl.flags.ignore_permissions = True
            gl.insert()

        self.db_set("posted_to_gl", 1)
        self.db_set("posted_on", now_datetime())
        frappe.db.commit()

    def post_to_ledger(self):
        """
        Backward compatibility method - calls the new idempotent version.
        """
        self.post_to_ledger_if_needed()

    # --------------------------
    # REPAYMENT SCHEDULE
    # --------------------------
    def create_repayment_schedule_if_needed(self):
        """
        Generate EMI-style repayment schedule once, after disbursement.
        Uses logic similar to your create_repayment_schedule().
        """
        if self.get("repayment_schedule"):
            # already has rows
            return

        principal = flt(self.loan_amount)
        months = int(self.loan_period_months)
        start_date = self.repayment_start_date or add_months(self.disbursement_date or today(), 1)

        # monthly flat interest rate
        monthly_interest_rate = flt(self.interest_rate) / 100.0 / 12.0

        # EMI calc
        if monthly_interest_rate > 0:
            emi = principal * monthly_interest_rate * ((1 + monthly_interest_rate) ** months) / (
                ((1 + monthly_interest_rate) ** months) - 1
            )
        else:
            emi = principal / months

        outstanding = principal
        pay_date = start_date

        for i in range(1, months + 1):
            interest_component = outstanding * monthly_interest_rate
            principal_component = emi - interest_component
            outstanding -= principal_component

            self.append("repayment_schedule", {
                "installment_no": i,
                "due_date": pay_date,
                "principal_amount": round(principal_component, 2),
                "interest_amount": round(interest_component, 2),
                "total_payment": round(emi, 2),
                "total_due": round(emi, 2),            # aligns with SHGLoanRepaymentSchedule.total_due
                "amount_paid": 0,
                "unpaid_balance": round(emi, 2),
                "balance_amount": round(outstanding, 2),
                "status": "Pending"
            })

            pay_date = add_months(pay_date, 1)

        # Update the balance_amount field on the parent loan
        self.db_set("balance_amount", round(outstanding, 2))

        frappe.msgprint(_("Repayment schedule generated with {0} installments.").format(months))

    def create_repayment_schedule(self):
        """
        Backward compatibility method - calls the new idempotent version.
        """
        self.create_repayment_schedule_if_needed()

    # --------------------------
    # OUTSTANDING & STATUS HELPERS
    # --------------------------
    def update_outstanding_balance_preview(self):
        """
        Compute outstanding balance based on schedule rows.
        Could be extended to consider actual repayments.
        """
        # For now, we'll just use the loan amount as a preview
        # In a more advanced implementation, this would calculate based on actual repayments
        if not self.balance_amount and self.loan_amount:
            self.balance_amount = flt(self.loan_amount)


def create_or_verify_member_account(member_id, company):
    """Ensure the member has a personal ledger account under SHG Members - <abbr>."""
    company_abbr = frappe.db.get_value("Company", company, "abbr")
    if not company_abbr:
        frappe.throw(f"Company abbreviation not found for {company}")

    parent_name = f"SHG Members - {company_abbr}"

    # Check for parent group
    parent_account = frappe.db.exists(
        "Account",
        {"account_name": parent_name, "company": company, "is_group": 1},
    )
    if not parent_account:
        # Create if missing under Accounts Receivable
        ar_account = frappe.db.get_value(
            "Account", {"account_name": f"Accounts Receivable - {company_abbr}"}, "name"
        )
        if not ar_account:
            frappe.throw(
                f"Accounts Receivable - {company_abbr} not found for {company}. Please create it first."
            )

        parent_account = frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": parent_name,
                "parent_account": ar_account,
                "is_group": 1,
                "company": company,
                "account_type": "Receivable",
            }
        ).insert(ignore_permissions=True)

    # Check if member subaccount exists
    member_account = frappe.db.exists(
        "Account",
        {"account_name": f"{member_id} - {company}", "company": company},
    )

    if not member_account:
        frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": f"{member_id} - {company}",
                "parent_account": parent_name,
                "is_group": 0,
                "company": company,
                "account_type": "Receivable",
            }
        ).insert(ignore_permissions=True)

    frappe.db.commit()


@frappe.whitelist()
def generate_individual_loans(parent_loan):
    """
    API endpoint to generate individual loans from a group loan.
    """
    parent = frappe.get_doc("SHG Loan", parent_loan)
    # Determine if this is a group loan based on presence of loan_members
    is_group_loan = bool(parent.get("loan_members"))

    if not is_group_loan:
        frappe.throw(_("This is not a group loan."))

    created_loans = parent.generate_individual_member_loans()
    
    frappe.db.commit()
    return {"created": created_loans}


# --- Hook functions ---
# These are hook functions called from hooks.py and should NOT have @frappe.whitelist()
def validate_loan(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()


def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    if doc.docstatus == 1 and not doc.get("posted_to_gl"):
        doc.post_to_ledger_if_needed()


def before_save(doc, method=None):
    """Ensure total loan amount = sum of allocations before save"""
    # Determine if this is a group loan based on presence of loan_members
    is_group_loan = bool(doc.get("loan_members"))

    if is_group_loan and getattr(doc, "loan_members", None):
        total_allocated = sum([flt(m.allocated_amount) for m in doc.loan_members])
        doc.loan_amount = total_allocated or 0


def after_insert_or_update(doc):
    """Automatically create individual loans when a group loan is saved or submitted"""
    if not getattr(doc, "loan_members", None):
        return

    # Determine if this is a group loan based on presence of loan_members
    is_group_loan = bool(doc.get("loan_members"))

    # Only for group loans
    if not is_group_loan:
        return

    created = []
    for m in doc.loan_members:
        # Skip if missing member or already exists
        if not m.member:
            frappe.msgprint(f"⚠️ Skipping one row — missing member in Loan Members table.")
            continue

        if frappe.db.exists("SHG Loan", {"parent_loan": doc.name, "member": m.member}):
            continue

        # Safely fetch member name if not already filled
        member_name = m.member_name
        if not member_name:
            member_name = frappe.db.get_value("SHG Member", m.member, "member_name")

        # Create individual loan
        new_loan = frappe.new_doc("SHG Loan")
        new_loan.update({
            "loan_type": doc.loan_type,
            "loan_amount": flt(m.allocated_amount) or flt(doc.loan_amount),
            "interest_rate": doc.interest_rate,
            "interest_type": doc.interest_type,
            "loan_period_months": doc.loan_period_months,
            "repayment_frequency": doc.repayment_frequency,
            "member": m.member,
            "member_name": member_name or "",
            "company": doc.company,
            "repayment_start_date": doc.repayment_start_date,
            "status": "Applied",
            "parent_loan": doc.name,
            "is_group_loan": 0
        })

        # Prevent insert if still missing member (safety net)
        if not new_loan.member:
            frappe.msgprint(f"⚠️ Skipped creating loan — missing member for child row.")
            continue

        new_loan.insert(ignore_permissions=True)
        created.append(new_loan.name)

    if created:
        frappe.msgprint(
            f"✅ Created {len(created)} individual loan(s):<br>{', '.join(created)}",
            alert=True
        )
        frappe.db.commit()


def on_submit(doc, method=None):
    before_save(doc)
    after_insert_or_update(doc)


def on_update_after_submit(doc, method=None):
    before_save(doc)
    after_insert_or_update(doc)


def after_insert(doc, method=None):
    before_save(doc)
    after_insert_or_update(doc)