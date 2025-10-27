import frappe
from frappe import _

def execute():
    """Validate and fix SHG Members account references"""
    try:
        # Get all companies
        companies = frappe.get_all("Company", fields=["name", "abbr"])
        
        for company in companies:
            company_name = company.name
            company_abbr = company.abbr
            
            # Build correct account path dynamically
            expected_parent_account = f"SHG Members - {company_abbr}"
            
            # Verify the account exists
            if not frappe.db.exists("Account", expected_parent_account):
                # Try to find the account with plain name
                plain_account = frappe.db.exists("Account", {
                    "account_name": "SHG Members",
                    "company": company_name
                })
                
                if not plain_account:
                    frappe.log(f"SHG Members account not found for company {company_name}. It will be created when needed.")
                else:
                    frappe.log(f"SHG Members account found for company {company_name}: {plain_account}")
            else:
                frappe.log(f"SHG Members account already exists for company {company_name}: {expected_parent_account}")
                
        frappe.log("SHG Members account validation completed successfully")
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error in patch_validate_shg_members_account")
        raise e