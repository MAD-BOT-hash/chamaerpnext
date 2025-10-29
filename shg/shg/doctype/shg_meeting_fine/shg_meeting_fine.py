import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, getdate

class SHGMeetingFine(Document):
    def validate(self):
        self.validate_fine_reason()
        self.validate_amount()
        self.validate_duplicate()
        self.autogenerate_description()
        
        # Ensure fine_amount is rounded to 2 decimal places
        if self.fine_amount:
            self.fine_amount = round(float(self.fine_amount), 2)
        
    def before_validate(self):
        """Ensure company is populated from SHG Settings."""
        from shg.shg.utils.company_utils import get_default_company
        if not getattr(self, "company", None):
            default_company = get_default_company()
            if default_company:
                self.company = default_company
            else:
                frappe.throw("Please set Default Company in SHG Settings before continuing.")

    def validate_fine_reason(self):
        """Validate that fine_reason is one of the allowed options"""
        allowed_reasons = ["Late Arrival", "Absentee", "Uniform Violation", "Noise Disturbance", "Other"]
        if self.fine_reason and self.fine_reason not in allowed_reasons:
            frappe.throw(_("Invalid Fine Reason. Must be one of: {0}").format(", ".join(allowed_reasons)))
            
    def autogenerate_description(self):
        """Auto-generate fine description if not provided"""
        if not self.fine_description and self.fine_reason and self.meeting:
            # Get meeting date
            meeting_date = frappe.db.get_value("SHG Meeting", self.meeting, "meeting_date")
            if meeting_date:
                self.fine_description = f"{self.fine_reason} fine for meeting on {meeting_date}"
        
    def validate_amount(self):
        """Validate fine amount"""
        if self.fine_amount <= 0:
            frappe.throw(_("Fine amount must be greater than zero"))
            
    def validate_duplicate(self):
        """Check for duplicate fines"""
        existing = frappe.db.exists("SHG Meeting Fine", {
            "member": self.member,
            "meeting": self.meeting,
            "fine_reason": self.fine_reason,
            "docstatus": 1,
            "name": ["!=", self.name]
        })
        if existing:
            frappe.throw(_("A fine already exists for this member for the same reason"))
            
    def on_submit(self):
        if self.status == "Paid":
            # ensure idempotent: if already posted -> skip
            if not self.get("posted_to_gl"):
                self.post_to_ledger()
            self.validate_gl_entries()
            
    def on_update(self):
        """Update status when paid date is set"""
        if self.paid_date and self.status != "Paid":
            self.status = "Paid"
            self.save()
            
    def validate_gl_entries(self):
        """Validate that GL entries were created properly"""
        if not self.journal_entry and not self.payment_entry:
            frappe.throw(_("Failed to create Journal Entry or Payment Entry for this meeting fine. Please check the system logs."))
            
        # Use validation utilities
        from shg.shg.utils.validation_utils import validate_reference_types_and_names, validate_custom_field_linking, validate_accounting_integrity
        validate_reference_types_and_names(self)
        validate_custom_field_linking(self)
        validate_accounting_integrity(self)
            
    def post_to_ledger(self):
        """
        Create a Payment Entry for this meeting fine.
        """
        # Add company source fallback
        if not self.company:
            settings_company = frappe.db.get_single_value("SHG Settings", "default_company")
            if not settings_company:
                frappe.throw("Default Company is missing in SHG Settings.")
            self.company = settings_company

        # Use the new account helper
        from shg.shg.utils.account_utils import get_account
        member_account = get_account(self.company, "fines", self.member)
        
        # Get customer for the member
        customer = frappe.db.get_value("SHG Member", self.member, "customer")
        
        # Get fine income account
        income_account = get_account(self.company, "fines")
        
        # Create journal entry with proper accounts
        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.company = self.company
        je.posting_date = self.paid_date or today()
        je.remark = f"Meeting fine from {self.member}"

        # Debit: member receivable
        je.append("accounts", {
            "account": member_account,
            "party_type": "Customer",
            "party": customer,
            "debit_in_account_currency": self.fine_amount,
            "credit_in_account_currency": 0,
            "company": self.company
        })

        # Credit: fines income account
        je.append("accounts", {
            "account": income_account,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": self.fine_amount,
            "company": self.company
        })

        je.insert(ignore_permissions=True)
        je.submit()
        
        # Update document with journal entry reference
        self.db_set("journal_entry", je.name)
        self.db_set("posted_to_gl", 1)
        frappe.db.commit()

    def get_fine_account(self, company):
        """Get fine income account, create if not exists"""
        from shg.shg.utils.account_utils import get_or_create_shg_penalty_income_account
        return get_or_create_shg_penalty_income_account(company)
        
    def get_member_account(self):
        """Get member's ledger account"""
        member = frappe.get_doc("SHG Member", self.member)
        company = frappe.defaults.get_user_default("Company")
        if not company:
            companies = frappe.get_all("Company", limit=1)
            if companies:
                company = companies[0].name
                
        from shg.shg.utils.account_utils import get_or_create_member_account
        return get_or_create_member_account(member, company)
        
    def get_member_customer(self):
        """Get member's customer link"""
        member = frappe.get_doc("SHG Member", self.member)
        return member.customer
        
    @frappe.whitelist()
    def send_fine_notification(self):
        """Send fine notification to member"""
        member = frappe.get_doc("SHG Member", self.member)
        
        message = f"Dear {member.member_name}, a fine of KES {self.fine_amount:,.2f} has been applied for {self.fine_reason.lower()}."
        
        notification = frappe.get_doc({
            "doctype": "SHG Notification Log",
            "member": self.member,
            "notification_type": "Meeting Fine",
            "message": message,
            "channel": "SMS",
            "reference_document": "SHG Meeting Fine",
            "reference_name": self.name
        })
        notification.insert()
        
        # Send SMS (would be implemented in actual system)
        # send_sms(member.phone_number, message)


# --- Hook functions ---
# These are hook functions called from hooks.py and should NOT have @frappe.whitelist()
def validate_fine(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()


def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    if doc.docstatus == 1 and doc.status == "Paid" and not doc.get("posted_to_gl"):
        doc.post_to_ledger()