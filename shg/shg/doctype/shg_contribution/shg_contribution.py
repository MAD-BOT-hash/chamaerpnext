import frappe
from frappe.model.document import Document
from frappe.utils import flt, today


class SHGContribution(Document):
    def validate(self):
        """Validate contribution data"""
        self.validate_member()
        self.validate_amount()
        self.set_member_name()

    def validate_member(self):
        """Validate member exists and is active"""
        if self.member:
            member_status = frappe.db.get_value("SHG Member", self.member, "membership_status")
            if member_status != "Active":
                frappe.throw(f"Cannot record contribution. Member {self.member} is not active.")

    def validate_amount(self):
        """Validate contribution amount"""
        if self.amount <= 0:
            frappe.throw("Contribution amount must be greater than zero.")

        # Check minimum contribution if it's a regular contribution
        if self.contribution_type in ["Regular Weekly", "Regular Monthly"]:
            try:
                settings = frappe.get_single("SHG Settings")
                min_amount = settings.default_contribution_amount or 0

                if self.amount < min_amount:
                    frappe.throw(f"Minimum contribution amount is KES {min_amount}")
            except frappe.DoesNotExistError:
                pass  # Settings may not exist yet

    def set_member_name(self):
        """Set member name from member link"""
        if self.member and not self.member_name:
            self.member_name = frappe.db.get_value("SHG Member", self.member, "member_name")

    def on_submit(self):
        """Post contribution to general ledger"""
        self.post_to_general_ledger()
        self.update_member_totals()

    def post_to_general_ledger(self):
        """Create journal entry for contribution"""
        company = self.safe_get_company()
        if not company:
            frappe.throw("No Company found. Please create a Company first.")

        # Account names
        cash_account = f"Cash - {company}"
        member_account = f"SHG Member - {self.member_name} - {company}"

        # Customer link
        customer = frappe.db.get_value("SHG Member", self.member, "customer_link")

        # Create journal entry
        je = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "posting_date": self.contribution_date,
            "company": company,
            "user_remark": f"Contribution from {self.member_name} - {self.contribution_type}",
            "accounts": [
                {
                    "account": cash_account,
                    "debit_in_account_currency": self.amount,
                    "reference_type": self.doctype,
                    "reference_name": self.name
                },
                {
                    "account": member_account,
                    "credit_in_account_currency": self.amount,
                    "party_type": "Customer" if customer else None,
                    "party": customer,
                    "reference_type": self.doctype,
                    "reference_name": self.name
                }
            ]
        })

        try:
            je.insert()
            je.submit()

            self.journal_entry = je.name
            self.posted_to_gl = 1
            self.db_update()
        except Exception as e:
            frappe.log_error(f"Failed to post to General Ledger: {str(e)}")

    def update_member_totals(self):
        """Update member's contribution totals"""
        try:
            member_doc = frappe.get_doc("SHG Member", self.member)
            if hasattr(member_doc, "update_financial_summary"):
                member_doc.update_financial_summary()
        except Exception as e:
            frappe.log_error(f"Failed to update member totals: {str(e)}")

    def on_cancel(self):
        """Cancel journal entry when contribution is cancelled"""
        if self.journal_entry:
            try:
                je = frappe.get_doc("Journal Entry", self.journal_entry)
                if je.docstatus == 1:
                    je.cancel()
            except Exception as e:
                frappe.log_error(f"Failed to cancel journal entry: {str(e)}")

        self.update_member_totals()

    @staticmethod
    def safe_get_company():
        """Helper to safely get a company name"""
        company = frappe.defaults.get_global_default("company")
        if company:
            return company

        companies = frappe.get_all("Company", fields=["name"], limit=1)
        return companies[0].name if companies else None


# --- Hook functions ---
def validate_contribution(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()


def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    doc.post_to_general_ledger()
    doc.update_member_totals()

