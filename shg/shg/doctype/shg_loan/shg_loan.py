import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, add_months, flt, now_datetime

class SHGLoan(Document):

    def validate(self):
        """Validate core loan data before saving."""
        if not self.member:
            frappe.throw(_("Member is required."))
        if not self.loan_amount or self.loan_amount <= 0:
            frappe.throw(_("Loan Amount must be greater than zero."))
        if not self.interest_rate:
            frappe.throw(_("Interest Rate is required."))
        if not self.repayment_period:
            frappe.throw(_("Repayment period (in months) is required."))

        # Auto-fetch company if missing
        if not self.company:
            self.company = frappe.db.get_single_value("SHG Settings", "default_company")

    def on_submit(self):
        """Handle loan submission."""
        self.post_to_ledger()
        self.create_repayment_schedule()
        frappe.msgprint(_("Loan successfully posted to ledger and repayment schedule created."))

    # --------------------------------------------------
    # LEDGER POSTING
    # --------------------------------------------------
    def post_to_ledger(self):
        """Create GL Entries for the loan disbursement."""
        # Check if already posted
        if self.posted_to_gl:
            return
            
        company = self.company or frappe.db.get_single_value("SHG Settings", "default_company")
        if not company:
            frappe.throw(_("Please set Default Company in SHG Settings."))

        # Validate necessary accounts from SHG Settings
        settings = frappe.get_single("SHG Settings")
        loan_account = settings.default_loan_account
        receivable_account = settings.member_receivable_account

        if not loan_account or not receivable_account:
            frappe.throw(_("Please set Default Loan and Receivable Accounts in SHG Settings."))

        # Prepare GL entries
        gl_entries = [
            # Debit: Member Receivable Account (Loan Given)
            {
                "account": receivable_account,
                "party_type": "Customer",
                "party": self.member,
                "debit": self.loan_amount,
                "credit": 0,
                "voucher_type": "SHG Loan",
                "voucher_no": self.name,
                "company": company,
                "posting_date": self.disbursement_date or today(),
                "remarks": f"Loan disbursement for {self.member}"
            },
            # Credit: Loan Account (Cash/Bank or Loan Pool)
            {
                "account": loan_account,
                "debit": 0,
                "credit": self.loan_amount,
                "voucher_type": "SHG Loan",
                "voucher_no": self.name,
                "company": company,
                "posting_date": self.disbursement_date or today(),
                "remarks": f"Loan disbursement for {self.member}"
            }
        ]

        # Insert into GL Entry
        for entry in gl_entries:
            gl = frappe.new_doc("GL Entry")
            for k, v in entry.items():
                setattr(gl, k, v)
            gl.flags.ignore_permissions = True
            gl.insert()

        # Mark as posted
        self.db_set("posted_to_gl", 1)
        self.db_set("posted_on", now_datetime())
        
        frappe.db.commit()
        frappe.msgprint(_("GL Entries created for Loan {0}").format(self.name))

    # --------------------------------------------------
    # AUTOMATIC REPAYMENT SCHEDULE
    # --------------------------------------------------
    def create_repayment_schedule(self):
        """Auto-generate EMI repayment schedule after disbursement."""
        # Check if schedule already exists
        if self.repayment_schedule:
            frappe.msgprint(_("Repayment schedule already exists for this loan."))
            return

        # Compute monthly interest rate
        monthly_interest_rate = flt(self.interest_rate) / 100 / 12
        principal = flt(self.loan_amount)
        months = int(self.repayment_period)

        # Calculate EMI using standard formula
        if monthly_interest_rate > 0:
            emi = principal * monthly_interest_rate * ((1 + monthly_interest_rate) ** months) / (((1 + monthly_interest_rate) ** months) - 1)
        else:
            emi = principal / months

        outstanding = principal
        payment_date = self.first_repayment_date or add_months(self.disbursement_date or today(), 1)

        for i in range(1, months + 1):
            interest_component = outstanding * monthly_interest_rate
            principal_component = emi - interest_component
            outstanding -= principal_component

            # Add to child table
            self.append("repayment_schedule", {
                "installment_no": i,
                "due_date": payment_date,
                "principal_amount": round(principal_component, 2),
                "interest_amount": round(interest_component, 2),
                "total_payment": round(emi, 2),
                "total_due": round(emi, 2),
                "amount_paid": 0,
                "unpaid_balance": round(emi, 2),
                "balance_amount": round(outstanding, 2),
                "status": "Pending"
            })
            payment_date = add_months(payment_date, 1)

        frappe.msgprint(_("Repayment schedule generated with {0} installments.").format(months))

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
    parent = frappe.get_doc("SHG Loan", parent_loan)
    created_loans = []

    for m in parent.loan_members:
        # Skip if already linked
        existing = frappe.db.exists("SHG Loan", {"parent_loan": parent.name, "member": m.member})
        if existing:
            continue

        new_loan = frappe.new_doc("SHG Loan")
        new_loan.update({
            "loan_type": parent.loan_type,
            "loan_amount": m.allocated_amount or parent.loan_amount,
            "interest_rate": parent.interest_rate,
            "interest_type": parent.interest_type,
            "loan_period_months": parent.loan_period_months,
            "repayment_frequency": parent.repayment_frequency,
            "member": m.member,
            "member_name": m.member_name,
            "repayment_start_date": parent.repayment_start_date,
            "status": "Applied",
            "parent_loan": parent.name,
            "is_group_loan": 0  # Optional flag
        })
        new_loan.insert(ignore_permissions=True)
        created_loans.append(new_loan.name)

    frappe.db.commit()
    return {"created": created_loans}


def before_save(doc, method=None):
    """Ensure total loan amount = sum of allocations before save"""
    if getattr(doc, "is_group_loan", 0) and getattr(doc, "loan_members", None):
        total_allocated = sum([flt(m.allocated_amount) for m in doc.loan_members])
        doc.loan_amount = total_allocated or 0


def after_insert_or_update(doc):
    """Automatically create individual loans when a group loan is saved or submitted"""
    if not getattr(doc, "loan_members", None):
        return

    # Only for group loans
    if not getattr(doc, "is_group_loan", 0):
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

# --- Hook functions ---
# These are hook functions called from hooks.py and should NOT have @frappe.whitelist()
def validate_loan(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()

def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    if doc.docstatus == 1 and not doc.get("posted_to_gl"):
        doc.post_to_ledger()
