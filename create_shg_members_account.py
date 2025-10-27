"""
Script to manually create SHG Members parent account if it's missing.
"""

import frappe

def create_shg_members_account():
    """Create SHG Members parent account for the default company"""
    try:
        # Get the default company
        company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not company:
            print("No default company found in Global Defaults")
            return
            
        company_abbr = frappe.get_value("Company", company, "abbr")
        print(f"Company: {company}, Abbreviation: {company_abbr}")
        
        # Check if SHG Members account exists (both with and without suffix)
        account_name_suffixed = f"SHG Members - {company_abbr}"
        account_name_plain = "SHG Members"
        
        # Try to find existing account
        existing_account = frappe.db.exists("Account", account_name_suffixed)
        if not existing_account:
            existing_account = frappe.db.exists("Account", {"account_name": account_name_plain, "company": company})
        
        if not existing_account:
            print(f"Creating SHG Members account for company: {company}")
            # First, find the Accounts Receivable parent
            ar_parent = frappe.db.get_value("Account", {
                "account_name": "Accounts Receivable", 
                "company": company
            }, "name")
            
            if not ar_parent:
                ar_parent = frappe.db.get_value("Account", {
                    "account_name": f"Accounts Receivable - {company_abbr}", 
                    "company": company
                }, "name")
            
            if ar_parent:
                # Create the SHG Members group account
                account_doc = frappe.get_doc({
                    "doctype": "Account",
                    "company": company,
                    "account_name": "SHG Members",
                    "parent_account": ar_parent,
                    "account_type": "Receivable",
                    "is_group": 1,
                    "root_type": "Asset"
                })
                account_doc.insert()
                frappe.db.commit()
                print(f"Created SHG Members account: {account_doc.name}")
            else:
                print(f"Could not find Accounts Receivable parent account for company: {company}")
        else:
            print(f"SHG Members account already exists for company: {company}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_shg_members_account()