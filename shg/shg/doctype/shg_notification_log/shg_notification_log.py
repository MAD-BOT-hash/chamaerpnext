import frappe
from frappe.model.document import Document
from frappe.utils import now

class SHGNotificationLog(Document):
    def validate(self):
        """Validate notification data"""
        if self.member and not self.member_name:
            member_name = frappe.db.get_value("SHG Member", self.member, "member_name")
            if member_name:
                self.member_name = member_name

    def mark_as_sent(self):
        """Mark notification as sent"""
        self.status = "Sent"
        self.sent_date = now()
        # Avoid re-triggering full validation, just update DB fields
        self.db_update()

    def mark_as_failed(self, error_message):
        """Mark notification as failed"""
        self.status = "Failed"
        self.error_message = error_message
        self.db_update()