"""
Script to ensure SHG Members account exists for the default company.
This can be run manually if the account is missing.
"""

import frappe

def ensure_shg_members_account():
    """Ensure SHG Members account exists for the default company"""
    try:
        # Get the default company
        company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not company:
            companies = frappe.get_all("Company", limit=1)
            if companies:
                company = companies[0].name
            else:
                print("No company found in the system")
                return
                
        print(f"Checking SHG Members account for company: {company}")
        
        # Get company abbreviation
        company_abbr = frappe.get_value("Company", company, "abbr")
        print(f"Company abbreviation: {company_abbr}")
        
        # Check if SHG Members account exists
        account_name_suffixed = f"SHG Members - {company_abbr}"
        account_name_plain = "SHG Members"
        
        # Try to find existing account
        existing_account = frappe.db.exists("Account", account_name_suffixed)
        if not existing_account:
            existing_account = frappe.db.exists("Account", {"account_name": account_name_plain, "company": company})
        
        if existing_account:
            print(f"SHG Members account already exists: {existing_account}")
            return existing_account
        
        # Account doesn't exist, create it
        print("SHG Members account not found, creating it...")
        
        # Find the Accounts Receivable parent account
        ar_parent = frappe.db.get_value("Account", {
            "account_name": "Accounts Receivable", 
            "company": company
        }, "name")
        
        if not ar_parent:
            ar_parent = frappe.db.get_value("Account", {
                "account_name": f"Accounts Receivable - {company_abbr}", 
                "company": company
            }, "name")
        
        if not ar_parent:
            print(f"Could not find Accounts Receivable parent account for company: {company}")
            return None
            
        print(f"Found parent account: {ar_parent}")
        
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
        return account_doc.name
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    ensure_shg_members_account()