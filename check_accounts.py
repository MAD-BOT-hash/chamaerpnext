import frappe
import os
import sys

# Add the current directory to Python path
sys.path.append(os.getcwd())

def check_accounts():
    try:
        frappe.init(site='.')
        frappe.connect()
        
        # Check if the company exists
        companies = frappe.get_all('Company')
        print("Companies in system:")
        for company in companies:
            print(f"  - {company.name}")
            
        # Check default company
        default_company = frappe.db.get_single_value('Global Defaults', 'default_company')
        print(f"Default company: {default_company}")
        
        # Check if SHG Members account exists
        if default_company:
            account_name = f"SHG Members - {frappe.get_value('Company', default_company, 'abbr')}"
            account = frappe.db.exists('Account', account_name)
            print(f"SHG Members account ({account_name}): {'Exists' if account else 'Not found'}")
            
            # Also check with plain name
            plain_account = frappe.db.exists('Account', {'account_name': 'SHG Members', 'company': default_company})
            print(f"SHG Members account (plain name): {'Exists' if plain_account else 'Not found'}")
            
            if not account and not plain_account:
                print("Need to create SHG Members account")
                # Try to create the account
                create_shg_accounts(default_company)
        else:
            print("No default company found")
            
        frappe.db.commit()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def create_shg_accounts(company):
    """Create SHG-specific accounts"""
    try:
        company_abbr = frappe.get_value("Company", company, "abbr")
        print(f"Company abbreviation: {company_abbr}")

        # Ensure SHG Members group account exists
        parent_account_name = f"SHG Members - {company_abbr}"
        if not frappe.db.exists("Account", parent_account_name):
            print(f"Creating SHG Members account: {parent_account_name}")
            # Get parent account using frappe.db.get_value for robustness
            ar_parent = frappe.db.get_value("Account", {"account_name": "Accounts Receivable", "company": company}, "name")
            if not ar_parent:
                ar_parent = frappe.db.get_value("Account", {"account_name": f"Accounts Receivable - {company_abbr}", "company": company}, "name")
            
            if ar_parent:
                parent_account = frappe.get_doc({
                    "doctype": "Account",
                    "company": company,
                    "account_name": "SHG Members",
                    "parent_account": ar_parent,
                    "account_type": "Receivable",
                    "is_group": 1,
                    "root_type": "Asset"
                })
                parent_account.insert()
                print(f"Created SHG Members account: {parent_account.name}")
            else:
                print("Could not find Accounts Receivable parent account")
        else:
            print(f"SHG Members account already exists: {parent_account_name}")
    except Exception as e:
        print(f"Error creating accounts: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_accounts()