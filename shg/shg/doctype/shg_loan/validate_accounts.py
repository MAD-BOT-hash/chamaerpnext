import frappe

def validate_accounts(self):
    """Validate accounts for loan disbursement"""
    if not self.company:
        self.company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
        if not self.company:
            frappe.throw("Company is required to disburse this loan.")

def get_company_abbr(company):
    """Get company abbreviation"""
    return frappe.db.get_value("Company", company, "abbr")

def ensure_parent_loan_receivable(company):
    """Ensure parent loan receivable account exists and is a group account"""
    abbr = get_company_abbr(company)
    parent = f"SHG Loans receivable - {abbr}"
    
    if not frappe.db.exists("Account", parent):
        ar = f"Accounts Receivable - {abbr}"
        if not frappe.db.exists("Account", ar):
            frappe.throw(f"{ar} not found")
        frappe.get_doc({
            "doctype": "Account",
            "account_name": "SHG Loans receivable",
            "name": parent,
            "parent_account": ar,
            "company": company,
            "is_group": 1,
            "account_type": "Receivable"
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    else:
        # Ensure it's marked as a group account
        frappe.db.set_value("Account", parent, "is_group", 1)
    
    return parent

def ensure_member_receivable(company, member_id):
    """Ensure member receivable account exists under parent loan receivable"""
    parent = ensure_parent_loan_receivable(company)
    abbr = get_company_abbr(company)
    acc_name = f"{member_id} - {abbr}"
    
    if not frappe.db.exists("Account", acc_name):
        member_name = frappe.db.get_value("SHG Member", member_id, "member_name") or member_id
        frappe.get_doc({
            "doctype": "Account",
            "account_name": member_name,
            "name": acc_name,
            "parent_account": parent,
            "company": company,
            "is_group": 0,
            "account_type": "Receivable"
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    
    return acc_name

def validate_settings_defaults():
    """Validate that required settings defaults are configured"""
    settings = frappe.get_single("SHG Settings")
    
    if not getattr(settings, "default_loan_account", None):
        frappe.throw("Please set Default Loan Account in SHG Settings.")
    
    # Either bank or cash account must be set
    if not getattr(settings, "default_bank_account", None) and not getattr(settings, "default_cash_account", None):
        frappe.throw("Please set either Default Bank Account or Default Cash Account in SHG Settings.")
    
    return settings