def validate_accounts(self):
    """Validate accounts for loan disbursement"""
    if not self.company:
        self.company = frappe.defaults.get_user_default("Company") or "Pioneer Friends Group"
    if not self.company:
        frappe.throw("Company is required to disburse this loan.")