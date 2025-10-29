import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
    today,
    add_months,
    flt,
    now_datetime,
)

class SHGLoan(Document):
    """
    SHG Loan controller:
    - Supports group & individual member loans
    - Posts loan disbursement to General Ledger
    - Auto-generates repayment schedule
    - Tracks outstanding balances
    """

    # --------------------------
    # VALIDATION
    # --------------------------
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

        # Round values
        if self.monthly_installment:
            self.monthly_installment = round(flt(self.monthly_installment), 2)
        if self.total_payable:
            self.total_payable = round(flt(self.total_payable), 2)

    # --------------------------
    # GROUP LOGIC
    # --------------------------
    def sync_group_allocations_total(self):
        total_allocated = sum(flt(row.allocated_amount) for row in self.get("loan_members", []))
        self.loan_amount = total_allocated or 0

    def generate_individual_member_loans(self):
        if not self.get("loan_members"):
            frappe.throw(_("This is not a group loan."))

        created = []
        for m in self.get("loan_members", []):
            if not m.member:
                continue
            if frappe.db.exists("SHG Loan", {"parent_loan": self.name, "member": m.member}):
                continue

            new_loan = frappe.new_doc("SHG Loan")
            new_loan.update({
                "loan_type": self.loan_type,
                "loan_amount": flt(m.allocated_amount),
                "interest_rate": self.interest_rate,
                "interest_type": self.interest_type,
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
        settings = frappe.get_single("SHG Settings")
        min_savings = flt(getattr(settings, "min_savings_for_loan", 0))

        def _check(member_id):
            member_doc = frappe.get_doc("SHG Member", member_id)
            if getattr(member_doc, "membership_status", "Active") != "Active":
                frappe.throw(_("{0} is not Active.").format(member_doc.member_name))
            if min_savings and flt(member_doc.total_contributions or 0) < min_savings:
                frappe.throw(_("{0} has not met minimum savings.").format(member_doc.member_name))

        if self.get("loan_members"):
            for r in self.loan_members:
                if r.member:
                    _check(r.member)
        elif self.member:
            _check(self.member)

    # --------------------------
    # POST TO LEDGER
    # --------------------------
    def post_to_ledger_if_needed(self):
        """Post loan disbursement Journal Entry."""
        if getattr(self, "posted_to_gl", 0):
            return

        company = self.company or frappe.db.get_single_value("SHG Settings", "company")
        company_abbr = frappe.db.get_value("Company", company, "abbr")
        settings = frappe.get_single("SHG Settings")
        loan_source_account = getattr(settings, "default_loan_account", None)
        if not loan_source_account:
            frappe.throw(_("Please set Default Loan Account in SHG Settings."))

        # Ensure parent & member account exist
        def ensure_parent():
            parent_name = f"SHG Loans receivable - {company_abbr}"
            if not frappe.db.exists("Account", parent_name):
                ar_parent = frappe.db.exists("Account", f"Accounts Receivable - {company_abbr}")
                if not ar_parent:
                    frappe.throw(_("Accounts Receivable - {0} not found.").format(company))
                frappe.get_doc({
                    "doctype": "Account",
                    "account_name": "SHG Loans receivable",
                    "name": parent_name,
                    "parent_account": f"Accounts Receivable - {company_abbr}",
                    "company": company,
                    "is_group": 1,
                    "account_type": "Receivable",
                }).insert(ignore_permissions=True)
                frappe.db.commit()
            else:
                frappe.db.set_value("Account", parent_name, "is_group", 1)
            return parent_name

        def ensure_member_account(member_id):
            parent = ensure_parent()
            acc_name = f"{member_id} - {company_abbr}"
            if not frappe.db.exists("Account", acc_name):
                member_name = frappe.db.get_value("SHG Member", member_id, "member_name") or member_id
                frappe.get_doc({
                    "doctype": "Account",
                    "account_name": member_name,
                    "name": acc_name,
                    "parent_account": parent,
                    "company": company,
                    "is_group": 0,
                    "account_type": "Receivable",
                }).insert(ignore_permissions=True)
                frappe.db.commit()
            return acc_name

        is_group_loan = bool(self.get("loan_members"))
        posting_date = self.disbursement_date or today()
        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.company = company
        je.posting_date = posting_date
        je.user_remark = f"Loan disbursement for {self.name}"

        if is_group_loan:
            for r in self.get("loan_members", []):
                if not r.member or not flt(r.allocated_amount):
                    continue
                member_acc = ensure_member_account(r.member)
                customer = frappe.db.get_value("SHG Member", r.member, "customer") or r.member
                je.append("accounts", {
                    "account": member_acc,
                    "party_type": "Customer",
                    "party": customer,
                    "debit_in_account_currency": flt(r.allocated_amount),
                    "company": company
                })
        else:
            member_acc = ensure_member_account(self.member)
            customer = frappe.db.get_value("SHG Member", self.member, "customer") or self.member
            je.append("accounts", {
                "account": member_acc,
                "party_type": "Customer",
                "party": customer,
                "debit_in_account_currency": flt(self.loan_amount),
                "company": company
            })

        total_disbursed = (
            sum(flt(r.allocated_amount) for r in self.get("loan_members", []))
            if is_group_loan else flt(self.loan_amount)
        )
        primary_member = self.member if not is_group_loan else self.loan_members[0].member
        customer = frappe.db.get_value("SHG Member", primary_member, "customer") or primary_member

        je.append("accounts", {
            "account": loan_source_account,
            "credit_in_account_currency": total_disbursed,
            "company": company,
            "party_type": "Customer",
            "party": customer
        })

        try:
            je.insert(ignore_permissions=True)
            je.submit()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Loan JE Posting Error")
            frappe.throw(_("Failed to post Journal Entry: {0}").format(e))

        self.db_set("journal_entry", je.name)
        self.db_set("posted_to_gl", 1)
        self.db_set("status", "Disbursed")
        frappe.msgprint(_(f"✅ Loan {self.name} posted to GL as {je.name}"))

    # --------------------------
    # REPAYMENT SCHEDULE
    # --------------------------
    def create_repayment_schedule_if_needed(self):
        """Auto-generate repayment schedule."""
        if self.get("repayment_schedule"):
            return

        principal = flt(self.loan_amount)
        months = int(self.loan_period_months)
        start_date = self.repayment_start_date or add_months(self.disbursement_date or today(), 1)
        interest_type = getattr(self, "interest_type", "Reducing Balance") or "Reducing Balance"

        if interest_type == "Flat Rate":
            self._generate_flat_rate_schedule(principal, months, start_date)
        else:
            self._generate_reducing_balance_schedule(principal, months, start_date)

        frappe.msgprint(_("✅ Repayment schedule generated with {0} installments.").format(months))

    def _generate_flat_rate_schedule(self, principal, months, start_date):
        rate = flt(self.interest_rate)
        total_interest = principal * (rate / 100) * (months / 12)
        total_payable = principal + total_interest
        monthly_install = total_payable / months if months else 0
        principal_component = principal / months if months else 0
        interest_component = monthly_install - principal_component
        outstanding = principal
        pay_date = start_date

        for i in range(1, months + 1):
            outstanding -= principal_component
            self.append("repayment_schedule", {
                "installment_no": i,
                "due_date": pay_date,
                "principal_amount": round(principal_component, 2),
                "interest_amount": round(interest_component, 2),
                "total_payment": round(monthly_install, 2),
                "loan_balance": round(outstanding, 2),
                "status": "Pending"
            })
            pay_date = add_months(pay_date, 1)
        self.db_set("balance_amount", round(principal, 2))

    def _generate_reducing_balance_schedule(self, principal, months, start_date):
        r = flt(self.interest_rate) / 100.0 / 12.0
        emi = principal * r * ((1 + r) ** months) / (((1 + r) ** months) - 1) if r else principal / months
        outstanding = principal
        pay_date = start_date

        for i in range(1, months + 1):
            interest = outstanding * r
            principal_part = emi - interest
            outstanding -= principal_part
            self.append("repayment_schedule", {
                "installment_no": i,
                "due_date": pay_date,
                "principal_amount": round(principal_part, 2),
                "interest_amount": round(interest, 2),
                "total_payment": round(emi, 2),
                "loan_balance": round(outstanding, 2),
                "status": "Pending"
            })
            pay_date = add_months(pay_date, 1)
        self.db_set("balance_amount", round(principal, 2))

    # --------------------------
    # PAYMENT ENTRY CREATION
    # --------------------------
    def _create_loan_payment_entry(self, repayment_schedule_item, payment_amount):
        """
        Create a Payment Entry for a loan repayment.
        This method is called by SHGLoanRepaymentSchedule.mark_as_paid().
        """
        from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

        # Get settings
        settings = frappe.get_single("SHG Settings")
        company = getattr(self, 'company', None) or frappe.db.get_single_value("SHG Settings", "company")

        if not company:
            frappe.throw(_("Please set Default Company in SHG Settings."))

        # Create payment entry
        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive"
        pe.company = company
        pe.posting_date = frappe.utils.today()
        pe.paid_amount = payment_amount
        pe.received_amount = payment_amount
        pe.allocate_payment_amount = 1

        # Set party details
        member = frappe.get_doc("SHG Member", self.member)
        pe.party_type = "Customer"
        pe.party = member.customer

        # Set accounts
        pe.paid_from = settings.default_receivable_account
        pe.paid_to = settings.default_bank_account or settings.default_cash_account

        # Add reference to this loan
        pe.append("references", {
            "reference_doctype": "SHG Loan",
            "reference_name": self.name,
            "total_amount": self.loan_amount,
            "outstanding_amount": self.balance_amount,
            "allocated_amount": payment_amount
        })

        pe.insert(ignore_permissions=True)
        pe.submit()

        # Link the payment entry to the repayment schedule item
        repayment_schedule_item.db_set("payment_entry", pe.name)

        return pe

    # --------------------------
    # OUTSTANDING BALANCE MANAGEMENT
    # --------------------------
    def recalculate_outstanding_after_payment(self):
        """
        Recalculate the outstanding balance on the loan after a payment is made.
        """
        total_paid = 0
        for schedule_item in self.get("repayment_schedule", []):
            total_paid += flt(schedule_item.amount_paid)

        self.balance_amount = flt(self.loan_amount) - total_paid
        self.db_set("balance_amount", self.balance_amount)

        # Update loan status based on balance
        if self.balance_amount <= 0:
            self.db_set("status", "Paid")
        elif self.balance_amount < flt(self.loan_amount):
            self.db_set("status", "Partially Paid")


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
            "company": getattr(doc, 'company', None) or frappe.db.get_single_value("SHG Settings", "company"),
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