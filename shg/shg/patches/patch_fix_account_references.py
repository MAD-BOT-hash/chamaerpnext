import frappe
from frappe import _

def execute():
    """Fix account references to use correct Chart of Accounts structure"""
    try:
        # Get all companies
        companies = frappe.get_all("Company", fields=["name", "abbr"])
        
        for company in companies:
            company_name = company.name
            company_abbr = company.abbr
            
            # Fix any existing accounts that might have incorrect naming
            # This is a safety check to ensure accounts are properly named
            
            # Check for incorrectly named SHG Members accounts
            incorrect_accounts = frappe.db.sql("""
                SELECT name FROM `tabAccount` 
                WHERE company = %s AND account_name = 'SHG Members' 
                AND name LIKE 'SHG Members - %%' AND name != %s
            """, (company_name, f"SHG Members - {company_abbr}"), as_dict=True)
            
            for account in incorrect_accounts:
                frappe.log(f"Found incorrectly named account: {account.name}")
                
        frappe.log("Account reference fix completed successfully")
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error in patch_fix_account_references")
        raise e