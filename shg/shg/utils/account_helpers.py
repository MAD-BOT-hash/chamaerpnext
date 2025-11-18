import frappe

def get_or_create_member_receivable(member_id, company):
    """Return or create a member-specific receivable subaccount under SHG Loans receivable - <abbr>."""
    if not member_id:
        frappe.throw("Member ID is required to get or create receivable account.")

    # --- Handle case when company is None with proper fallbacks ---
    if not company:
        # Try to get company from SHG Settings
        company = frappe.db.get_single_value("SHG Settings", "company")
        
    if not company:
        # Try to get company from user defaults
        company = frappe.defaults.get_user_default("Company")
        
    if not company:
        # Try to get default company from Global Defaults
        company = frappe.db.get_single_value("Global Defaults", "default_company")
        
    if not company:
        # Get first available company
        companies = frappe.get_all("Company", limit=1)
        if companies:
            company = companies[0].name
            
    if not company:
        frappe.throw("Company is required but could not be determined. Please set a company in SHG Settings or Global Defaults.")

    # --- Get company abbreviation ---
    abbr = frappe.db.get_value("Company", company, "abbr")
    if not abbr:
        frappe.throw(f"Company abbreviation not found for {company}")

    parent_account = f"SHG Loans receivable - {abbr}"

    # --- Ensure parent account exists and is_group = 1 ---
    if not frappe.db.exists("Account", parent_account):
        frappe.throw(f"Parent account {parent_account} missing. Please create it under Accounts Receivable - {abbr}.")
    
    frappe.db.set_value("Account", parent_account, "is_group", 1)

    # --- Get member info ---
    member_name = frappe.db.get_value("SHG Member", member_id, "member_name") or member_id
    account_name = f"{member_name.strip().upper()} - {abbr}"

    # --- If subaccount missing, create it ---
    if not frappe.db.exists("Account", {"account_name": account_name, "company": company}):
        child = frappe.get_doc({
            "doctype": "Account",
            "account_name": account_name,
            "parent_account": parent_account,
            "company": company,
            "account_type": "Receivable",
            "is_group": 0,
            "root_type": "Asset",
            "report_type": "Balance Sheet"
        })
        child.insert(ignore_permissions=True)
        frappe.msgprint(f"✅ Created subaccount {account_name} under {parent_account}")
        return child.name

    return frappe.db.get_value("Account", {"account_name": account_name, "company": company}, "name")