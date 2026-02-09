import frappe
from frappe.model.document import Document

class SHGScheduledNotification(Document):
    def validate(self):
        """Validate scheduled notification"""
        if not self.member:
            frappe.throw("Member is required")
        
        if not self.scheduled_date:
            frappe.throw("Scheduled date is required")
        
        if not self.message:
            frappe.throw("Message is required")
    
    def before_save(self):
        """Set member name if not already set"""
        if self.member and not self.member_name:
            member_name = frappe.db.get_value("SHG Member", self.member, "member_name")
            if member_name:
                self.member_name = member_name