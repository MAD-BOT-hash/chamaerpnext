# Copyright (c) 2026, SHG Solutions
# License: MIT

import frappe
from frappe.model.document import Document

class SHGEmailLog(Document):
    def before_insert(self):
        """Set default values before inserting"""
        if not self.sent_by:
            self.sent_by = frappe.session.user
        
        if not self.sent_on:
            from frappe.utils import now
            self.sent_on = now()
    
    def validate(self):
        """Validate email log entry"""
        # Ensure required fields are present
        if not self.member:
            frappe.throw("Member is required")
        
        if not self.email_address:
            frappe.throw("Email address is required")
        
        if not self.subject:
            frappe.throw("Subject is required")
        
        if not self.status:
            frappe.throw("Status is required")
        
        if not self.document_type:
            frappe.throw("Document type is required")
    
    def on_update(self):
        """Actions to perform when document is updated"""
        # Log any status changes
        if self.has_value_changed("status"):
            frappe.log_info(f"Email log status changed for {self.name}: {self.status}")