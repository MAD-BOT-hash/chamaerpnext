import frappe
from frappe.model.document import Document

class SHGSettings(Document):
    def validate(self):
        """Validate SHG settings"""
        if self.default_contribution_amount < 0:
            frappe.throw("Default contribution amount cannot be negative")
            
        if self.default_interest_rate < 0 or self.default_interest_rate > 100:
            frappe.throw("Interest rate must be between 0 and 100 percent")
            
        if self.penalty_rate < 0 or self.penalty_rate > 100:
            frappe.throw("Penalty rate must be between 0 and 100 percent")
            
        # Validate Mpesa settings if enabled
        if self.mpesa_enabled:
            if not self.mpesa_consumer_key:
                frappe.throw("Mpesa Consumer Key is required")
            if not self.mpesa_consumer_secret:
                frappe.throw("Mpesa Consumer Secret is required")
            if not self.mpesa_shortcode:
                frappe.throw("Mpesa Shortcode is required")
            if not self.mpesa_passkey:
                frappe.throw("Mpesa Passkey is required")