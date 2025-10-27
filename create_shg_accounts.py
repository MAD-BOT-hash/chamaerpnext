"""
Script to manually create SHG Members parent account if it's missing.
Run this script from the bench console or as a patch.
"""

import frappe

def create_shg_members_account():
    """Create SHG Members parent account for all companies"""
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
                print(f"Creating SHG Members account for company: {company_name}")
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
                    print(f"Created SHG Members account: {account_doc.name}")
                else:
                    print(f"Could not find Accounts Receivable parent account for company: {company_name}")
            else:
                print(f"SHG Members account already exists for company: {company_name}")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_shg_members_account()