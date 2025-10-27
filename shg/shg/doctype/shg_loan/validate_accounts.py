import frappe

def validate_accounts(self):
    """Validate accounts for loan disbursement"""
    if not self.company:
        self.company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
        if not self.company:
            frappe.throw("Company is required to disburse this loan.")