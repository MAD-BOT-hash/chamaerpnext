import frappe
from frappe.model.document import Document

class SHGContributionType(Document):
    def validate(self):
        if self.is_billable:
            if not self.billing_frequency:
                frappe.throw("Billing Frequency is required for billable contributions")
            if not self.due_day:
                frappe.throw("Due Day is required for billable contributions")
            if self.due_day < 1 or self.due_day > 31:
                frappe.throw("Due Day must be between 1 and 31")
            if not self.item_code:
                frappe.throw("Item Code is required for billable contributions")