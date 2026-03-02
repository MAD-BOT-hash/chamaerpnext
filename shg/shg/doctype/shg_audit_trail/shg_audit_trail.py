import frappe
from frappe.model.document import Document


class SHGAuditTrail(Document):
    """SHG Audit Trail Document"""
    
    def validate(self):
        """Validate audit trail entry"""
        # Ensure timestamp is not in future
        if self.timestamp > frappe.utils.now_datetime():
            frappe.throw("Audit timestamp cannot be in the future")
        
        # Validate JSON details if present
        if self.details:
            try:
                import json
                json.loads(self.details)
                self.details_json = self.details
            except json.JSONDecodeError:
                frappe.throw("Invalid JSON in details field")