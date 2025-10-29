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
        if not getattr(self, 'company', None):
            self.company = frappe.db.get_single_value("SHG Settings", "company")

        # If this is a group loan, force total = sum of allocations
        if is_group_loan:
            self.sync_group_allocations_total()

        # Check eligibility for each member (group loan) or the single loan member
        self.run_eligibility_checks()

        # Ensure monetary values are rounded to 2 decimal places
        if self.monthly_installment:
            self.monthly_installment = round(float(self.monthly_installment), 2)
        if self.total_payable:
            self.total_payable = round(float(self.total_payable), 2)

        # Check if loan terms have changed and update repayment schedule if needed
        if self.docstatus == 0:  # Only for draft documents
            self._check_and_update_repayment_schedule()

    def _check_and_update_repayment_schedule(self):
        """
        Check if loan terms have changed and update repayment schedule accordingly.
        Only applies to draft loans that already have a repayment schedule.
        """
        if not self.get("repayment_schedule"):
            return

        # Check if any key loan parameters have changed
        dirty_fields = getattr(self, "_dirty_fields", set())
        key_fields = {"loan_amount", "interest_rate", "loan_period_months", "interest_type", "repayment_start_date"}
        
        if dirty_fields.intersection(key_fields):
            # Save old values for audit log
            old_values = {
                "loan_amount": self.get_doc_before_save().loan_amount if self.get_doc_before_save() else self.loan_amount,
                "interest_rate": self.get_doc_before_save().interest_rate if self.get_doc_before_save() else self.interest_rate,
                "loan_period_months": self.get_doc_before_save().loan_period_months if self.get_doc_before_save() else self.loan_period_months,
                "interest_type": self.get_doc_before_save().interest_type if self.get_doc_before_save() else self.interest_type,
                "repayment_start_date": self.get_doc_before_save().repayment_start_date if self.get_doc_before_save() else self.repayment_start_date
            }
            
            # Update the repayment schedule
            self.update_repayment_schedule()
            
            # Add detailed audit log
            self.add_comment("Edit", f"Repayment schedule updated due to loan term changes. "
                          f"Loan Amount: {old_values['loan_amount']} → {self.loan_amount}, "
                          f"Interest Rate: {old_values['interest_rate']}% → {self.interest_rate}%, "
                          f"Period: {old_values['loan_period_months']} → {self.loan_period_months} months, "
                          f"Interest Type: {old_values['interest_type']} → {self.interest_type}")

    def on_update(self):
        """
        Called when document is updated.
        """
        # For submitted documents, if key fields change, we need to handle repayment schedule updates
        if self.docstatus == 1:
            self._handle_submitted_loan_updates()

    def _handle_submitted_loan_updates(self):
        """
        Handle updates to submitted loans that might affect the repayment schedule.
        """
        # This would be called if allow_on_submit fields are updated
        # For now, we'll just ensure the repayment schedule is consistent
        pass

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
    # REPAYMENT CALCULATION
    # --------------------------
    @frappe.whitelist()
    def calculate_repayment_details(self):
        """
        Calculate monthly installment and total payable amount based on loan parameters.
        This method is called from the frontend via JavaScript.
        """
        if not self.loan_amount or not self.interest_rate or not self.loan_period_months:
            return {
                "monthly_installment": 0,
                "total_payable": 0
            }

        principal = flt(self.loan_amount)
        months = int(self.loan_period_months)
        annual_interest_rate = flt(self.interest_rate)

        # Calculate based on interest type
        interest_type = getattr(self, "interest_type", "Flat Rate") or "Flat Rate"

        if interest_type == "Flat Rate":
            # Flat rate calculation
            total_interest = principal * (annual_interest_rate / 100) * (months / 12)
            total_payable = principal + total_interest
            monthly_installment = total_payable / months if months > 0 else 0
        else:
            # Reducing balance calculation (EMI)
            monthly_interest_rate = annual_interest_rate / 100 / 12
            if monthly_interest_rate > 0:
                monthly_installment = principal * monthly_interest_rate * ((1 + monthly_interest_rate) ** months) / (
                    ((1 + monthly_interest_rate) ** months) - 1
                )
            else:
                monthly_installment = principal / months if months > 0 else 0
            total_payable = monthly_installment * months

        # Ensure monetary values are rounded to 2 decimal places
        monthly_installment = round(float(monthly_installment), 2)
        total_payable = round(float(total_payable), 2)

        return {
            "monthly_installment": monthly_installment,
            "total_payable": total_payable
        }

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
                "company": getattr(self, 'company', None) or frappe.db.get_single_value("SHG Settings", "company"),
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
        Post the loan disbursement to the General Ledger (Journal Entry)
        with full validation, auto-creation of member accounts, and
        fallback handling for missing customers or loan source accounts.
        Idempotent: runs once per loan.
        """

        # --- 1️⃣ Skip if already posted ---
        if getattr(self, "posted_to_gl", 0):
            frappe.msgprint(f"GL already posted for {self.name} ({self.journal_entry})", alert=True)
            return

        # --- 2️⃣ Resolve company ---
        company = getattr(self, "company", None) or frappe.db.get_single_value("SHG Settings", "company")
        if not company:
            frappe.throw(_("Company not set on loan or in SHG Settings."))

        company_abbr = frappe.db.get_value("Company", company, "abbr")
        if not company_abbr:
            frappe.throw(_("Company abbreviation not found for {0}.").format(company))

        # --- 3️⃣ Resolve SHG Settings defaults ---
        settings = frappe.get_single("SHG Settings")

        loan_source_account = getattr(settings, "default_loan_account", None)
        if not loan_source_account:
            frappe.throw(_("Please set 'Default Loan Account' in SHG Settings (e.g. Cash or Bank)."))

        # --- 4️⃣ Helper to ensure parent/group account exists ---
        def ensure_parent_loan_account():
            parent_name = f"SHG Loans receivable - {company_abbr}"
            parent_exists = frappe.db.exists("Account", parent_name)
            if not parent_exists:
                ar_parent = frappe.db.exists("Account", f"Accounts Receivable - {company_abbr}")
                if not ar_parent:
                    frappe.throw(
                        _(f"Accounts Receivable - {company_abbr} not found for {company}. "
                          f"Please create it in Chart of Accounts.")
                    )
                parent_doc = frappe.get_doc({
                    "doctype": "Account",
                    "account_name": "SHG Loans receivable",
                    "name": parent_name,
                    "parent_account": f"Accounts Receivable - {company_abbr}",
                    "company": company,
                    "is_group": 1,
                    "account_type": "Receivable",
                    "root_type": "Asset",
                }).insert(ignore_permissions=True)
                frappe.db.commit()
            else:
                # ensure marked as group
                is_group = frappe.db.get_value("Account", parent_name, "is_group")
                if not is_group:
                    frappe.db.set_value("Account", parent_name, "is_group", 1)
                    frappe.db.commit()
            return parent_name

        # --- 5️⃣ Helper to ensure per-member receivable account exists ---
        def ensure_member_account(member_id):
            if not member_id:
                frappe.throw(_("Loan Member is missing. Cannot post to GL."))

            parent_name = ensure_parent_loan_account()
            account_name = f"{member_id} - {company_abbr}"

            acc_exists = frappe.db.exists("Account", account_name)
            if not acc_exists:
                member_name = frappe.db.get_value("SHG Member", member_id, "member_name") or member_id
                acc_doc = frappe.get_doc({
                    "doctype": "Account",
                    "account_name": member_name,
                    "name": account_name,
                    "parent_account": parent_name,
                    "company": company,
                    "is_group": 0,
                    "account_type": "Receivable",
                    "root_type": "Asset",
                }).insert(ignore_permissions=True)
                frappe.db.commit()
                return acc_doc.name
            return account_name

        # --- 6️⃣ Determine loan type ---
        is_group_loan = bool(self.get("loan_members"))

        # --- 7️⃣ Build Journal Entry ---
        posting_date = self.disbursement_date or frappe.utils.today()

        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.company = company
        je.posting_date = posting_date
        je.user_remark = f"Loan disbursement for {self.name}"

        # --- 8️⃣ Post debit lines for loan receivable(s) ---
        if is_group_loan:
            allocations = self.get("loan_members", [])
            if not allocations:
                frappe.throw(_("No Loan Members found for group loan."))

            for row in allocations:
                if not row.member or not flt(row.allocated_amount):
                    continue

                member_account = ensure_member_account(row.member)
                customer = frappe.db.get_value("SHG Member", row.member, "customer") or row.member

                je.append("accounts", {
                    "account": member_account,
                    "party_type": "Customer",
                    "party": customer,
                    "debit_in_account_currency": flt(row.allocated_amount),
                    "credit_in_account_currency": 0,
                    "company": company,
                })

        else:
            # Individual loan
            member_account = ensure_member_account(self.member)
            customer = frappe.db.get_value("SHG Member", self.member, "customer") or self.member

            je.append("accounts", {
                "account": member_account,
                "party_type": "Customer",
                "party": customer,
                "debit_in_account_currency": flt(self.loan_amount),
                "credit_in_account_currency": 0,
                "company": company,
            })

        # --- 9️⃣ Add credit line (Loan Source / Cash) ---
        total_disbursed = flt(self.loan_amount)
        if is_group_loan:
            total_disbursed = sum(flt(r.allocated_amount) for r in self.get("loan_members", []))

        je.append("accounts", {
            "account": loan_source_account,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": total_disbursed,
            "company": company,
        })

        # --- 🔟 Insert + submit the JE ---
        try:
            je.insert(ignore_permissions=True)
            je.submit()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Loan JE Posting Error")
            frappe.throw(_("Failed to post Journal Entry: {0}").format(e))

        # --- 11️⃣ Update Loan status and link ---
        self.db_set("journal_entry", je.name)
        self.db_set("posted_to_gl", 1)
        self.db_set("posted_on", frappe.utils.now_datetime())
        self.db_set("status", "Disbursed")
        frappe.db.commit()

        frappe.msgprint(_(f"✅ Loan {self.name} successfully posted to GL as Journal Entry {je.name}."))

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
        Generate repayment schedule once, after disbursement.
        Supports both flat interest and reducing balance calculation methods.
        """
        if self.get("repayment_schedule"):
            # already has rows
            return

        principal = flt(self.loan_amount)
        months = int(self.loan_period_months)
        start_date = self.repayment_start_date or add_months(self.disbursement_date or today(), 1)

        # Get interest calculation method
        interest_type = getattr(self, "interest_type", "Reducing Balance") or "Reducing Balance"

        if interest_type == "Flat Rate":
            self._generate_flat_rate_schedule(principal, months, start_date)
        else:
            self._generate_reducing_balance_schedule(principal, months, start_date)

        frappe.msgprint(_("Repayment schedule generated with {0} installments.").format(months))

    def _generate_flat_rate_schedule(self, principal, months, start_date):
        """
        Generate repayment schedule using flat interest rate method.
        """
        annual_interest_rate = flt(self.interest_rate)
        total_interest = principal * (annual_interest_rate / 100) * (months / 12)
        total_payable = principal + total_interest
        monthly_installment = total_payable / months if months > 0 else 0

        # Principal component is fixed for flat rate
        principal_component = principal / months if months > 0 else 0
        interest_component = monthly_installment - principal_component

        outstanding = principal
        pay_date = start_date

        for i in range(1, months + 1):
            # For flat rate, principal and interest components are fixed
            self.append("repayment_schedule", {
                "installment_no": i,
                "due_date": pay_date,
                "principal_amount": round(principal_component, 2),
                "interest_amount": round(interest_component, 2),
                "total_payment": round(monthly_installment, 2),
                "total_due": round(monthly_installment, 2),
                "amount_paid": 0,
                "unpaid_balance": round(monthly_installment, 2),
                "balance_amount": round(outstanding - principal_component, 2),
                "status": "Pending"
            })

            outstanding -= principal_component
            pay_date = add_months(pay_date, 1)

        # Update the balance_amount field on the parent loan
        self.db_set("balance_amount", round(principal, 2))

    def _generate_reducing_balance_schedule(self, principal, months, start_date):
        """
        Generate repayment schedule using reducing balance method (EMI).
        """
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
                "total_due": round(emi, 2),
                "amount_paid": 0,
                "unpaid_balance": round(emi, 2),
                "balance_amount": round(outstanding, 2),
                "status": "Pending"
            })

            pay_date = add_months(pay_date, 1)

        # Update the balance_amount field on the parent loan
        self.db_set("balance_amount", round(principal, 2))

    def create_repayment_schedule(self):
        """
        Backward compatibility method - calls the new idempotent version.
        """
        self.create_repayment_schedule_if_needed()

    def update_repayment_schedule(self):
        """
        Update repayment schedule when loan terms are changed.
        This method should be called when loan parameters are modified.
        """
        # Clear existing schedule
        self.repayment_schedule = []
        
        # Regenerate schedule with new terms
        self.create_repayment_schedule_if_needed()
        
        # Add audit log
        self.add_comment("Edit", "Repayment schedule updated due to loan term changes")

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
    """
    Automatically handle post-creation logic for both group and individual loans:
      - For group loans: auto-create individual member loans.
      - For individual loans: auto-generate repayment schedule immediately.
    """
    is_group_loan = bool(doc.get("loan_members"))

    if is_group_loan:
        created = []
        for m in doc.get("loan_members", []):
            if not m.member:
                frappe.msgprint(f"⚠️ Skipping a row with no member.")
                continue

            # Skip if already created
            if frappe.db.exists("SHG Loan", {"parent_loan": doc.name, "member": m.member}):
                continue

            new_loan = frappe.new_doc("SHG Loan")
            new_loan.update({
                "loan_type": doc.loan_type,
                "loan_amount": flt(m.allocated_amount) or 0,
                "interest_rate": doc.interest_rate,
                "interest_type": doc.interest_type,
                "loan_period_months": doc.loan_period_months,
                "repayment_frequency": doc.repayment_frequency,
                "member": m.member,
                "member_name": m.member_name or frappe.db.get_value("SHG Member", m.member, "member_name"),
                "company": doc.company or frappe.db.get_single_value("SHG Settings", "company"),
                "repayment_start_date": doc.repayment_start_date or frappe.utils.today(),
                "status": "Applied",
                "parent_loan": doc.name,
                "is_group_loan": 0
            })
            new_loan.insert(ignore_permissions=True)
            created.append(new_loan.name)

        if created:
            frappe.msgprint(
                f"✅ Created {len(created)} individual loan(s): {', '.join(created)}",
                alert=True
            )
            frappe.db.commit()
    else:
        # Auto-generate repayment schedule for individual loans
        if not doc.get("repayment_schedule"):
            doc.create_repayment_schedule_if_needed()
            frappe.msgprint("✅ Repayment Schedule auto-generated for this loan.", alert=True)


def on_submit(doc, method=None):
    """
    On submit:
      - For group loans: block submission (handled via members).
      - For individual loans: mark as Disbursed, post to GL, and generate repayment schedule.
    """
    is_group_loan = bool(doc.get("loan_members"))

    if is_group_loan:
        frappe.throw(_("Group Loan cannot be submitted directly. Generate individual loans first."))

    # Post to ledger if not done
    doc.post_to_ledger_if_needed()

    # Always create repayment schedule if missing
    if not doc.get("repayment_schedule"):
        doc.create_repayment_schedule_if_needed()

    doc.db_set("status", "Disbursed")
    doc.db_set("disbursed_on", frappe.utils.now_datetime())

    frappe.msgprint(_("✅ Loan {0} disbursed and repayment schedule generated.").format(doc.name))


def on_update_after_submit(doc, method=None):
    before_save(doc)
    after_insert_or_update(doc)


def after_insert(doc, method=None):
    before_save(doc)
    after_insert_or_update(doc)