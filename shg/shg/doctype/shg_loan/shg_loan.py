import frappe
from frappe.model.document import Document
from frappe.utils import flt, today

class SHGLoan(Document):
    def validate(self):
        """Basic sanity checks before submission."""
        if not self.member:
            frappe.throw("Please select a Member for this loan.")

        if not self.loan_amount or self.loan_amount <= 0:
            frappe.throw("Loan Amount must be greater than zero.")

        # Initialize balance if not set
        if not self.balance_amount:
            self.balance_amount = self.loan_amount

        # Auto-set disbursement date if not provided
        if not self.disbursement_date:
            self.disbursement_date = today()

        # Ensure loan status consistency
        if not self.status:
            self.status = "Draft"

    def on_submit(self):
        """When the loan is submitted, mark as 'Disbursed' and create member account if needed."""
        self.status = "Disbursed"

        # Create member account under SHG Members - <abbr>
        create_or_verify_member_account(self.member, self.company)

        # Set initial balance
        if not self.balance_amount:
            self.balance_amount = self.loan_amount

        frappe.msgprint(f"Loan {self.name} disbursed successfully.")

    def on_cancel(self):
        """Revert to draft-like state on cancellation."""
        self.status = "Cancelled"
        frappe.msgprint(f"Loan {self.name} cancelled.")

    def update_balance(self, amount_paid):
        """Safe helper for repayment updates."""
        self.flags.ignore_validate_update_after_submit = True

        new_balance = flt(self.balance_amount or 0) - flt(amount_paid or 0)
        if new_balance < 0:
            frappe.throw("Repayment exceeds remaining balance.")

        self.balance_amount = new_balance
        self.last_repayment_date = today()
        self.status = "Paid" if new_balance == 0 else "Partially Paid"

        self.save(ignore_permissions=True)
        frappe.db.commit()

        self.add_comment(
            "Edit",
            f"Repayment of {amount_paid} applied. Remaining balance: {new_balance}"
        )


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

# --- Hook functions ---
# These are hook functions called from hooks.py and should NOT have @frappe.whitelist()
def validate_loan(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()

def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    if doc.docstatus == 1 and not doc.get("posted_to_gl"):
        doc.post_to_ledger()
