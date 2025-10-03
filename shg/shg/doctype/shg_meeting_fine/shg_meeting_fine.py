import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, getdate

class SHGMeetingFine(Document):
    def validate(self):
        self.validate_amount()
        self.validate_duplicate()
        
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
        from shg.shg.utils.gl_utils import create_meeting_fine_payment_entry, update_document_with_payment_entry
        payment_entry = create_meeting_fine_payment_entry(self)
        update_document_with_payment_entry(self, payment_entry)
        
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
def validate_fine(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()


def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    if doc.docstatus == 1 and doc.status == "Paid" and not doc.get("posted_to_gl"):
        doc.post_to_ledger()
