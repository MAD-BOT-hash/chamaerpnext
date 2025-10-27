import frappe
from frappe import _

def execute():
    """Create SHG Members parent account if it doesn't exist"""
    try:
        # Get all companies
        companies = frappe.get_all("Company", fields=["name", "abbr"])
        
        for company in companies:
            company_name = company.name
            company_abbr = company.abbr
            
            # Check if SHG Members account exists (both with and without suffix)
            account_name_suffixed = f"SHG Members - {company_abbr}"
            account_name_plain = "SHG Members"
            
            # Try to find existing account
            existing_account = frappe.db.exists("Account", account_name_suffixed)
            if not existing_account:
                existing_account = frappe.db.exists("Account", {"account_name": account_name_plain, "company": company_name})
            
            if not existing_account:
                # Create the SHG Members parent account
                # First, find the Accounts Receivable parent
                ar_parent = frappe.db.get_value("Account", {
                    "account_name": "Accounts Receivable", 
                    "company": company_name
                }, "name")
                
                if not ar_parent:
                    ar_parent = frappe.db.get_value("Account", {
                        "account_name": f"Accounts Receivable - {company_abbr}", 
                        "company": company_name
                    }, "name")
                
                if ar_parent:
                    # Create the SHG Members group account
                    account_doc = frappe.get_doc({
                        "doctype": "Account",
                        "company": company_name,
                        "account_name": "SHG Members",
                        "parent_account": ar_parent,
                        "account_type": "Receivable",
                        "is_group": 1,
                        "root_type": "Asset"
                    })
                    account_doc.insert()
                    frappe.db.commit()
                    frappe.log("Created SHG Members parent account for company: " + company_name)
                else:
                    frappe.log_error("Could not find Accounts Receivable parent account for company: " + company_name)
            else:
                frappe.log("SHG Members parent account already exists for company: " + company_name)
                
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error in patch_create_shg_members_account")
        raise e