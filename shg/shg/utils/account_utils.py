import frappe
from frappe import _

def create_parent_account(company, account_type, parent_account_name):
    """Create parent account if it doesn't exist"""
    company_abbr = frappe.db.get_value("Company", company, "abbr")
    
    # Determine parent account based on account type
    if account_type in ["members", "loans_receivable"]:
        # These go under Accounts Receivable
        ar_parent = frappe.db.get_value("Account", {"account_name": "Accounts Receivable", "company": company}, "name")
        if not ar_parent:
            ar_parent = frappe.db.get_value("Account", {"account_name": f"Accounts Receivable - {company_abbr}", "company": company}, "name")
        
        if not ar_parent:
            frappe.throw(f"No 'Accounts Receivable' group account found for {company}.")
            
        # Account properties based on type
        account_props = {
            "members": {
                "account_type": "Receivable",
                "is_group": 1,
                "root_type": "Asset"
            },
            "loans_receivable": {
                "account_type": "Receivable",
                "is_group": 1,
                "root_type": "Asset"
            }
        }
        
        props = account_props[account_type]
        
        # Create the parent account
        parent_doc = frappe.get_doc({
            "doctype": "Account",
            "account_name": parent_account_name.split(" - ")[0],  # Remove company suffix
            "company": company,
            "parent_account": ar_parent,
            "is_group": props["is_group"],
            "account_type": props["account_type"],
            "report_type": "Balance Sheet" if props["root_type"] == "Asset" else "Profit and Loss",
            "root_type": props["root_type"]
        })
        parent_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
    elif account_type in ["contributions", "income", "fines"]:
        # These go under Income
        income_parent = frappe.db.get_value("Account", {"account_name": "Income", "company": company}, "name")
        if not income_parent:
            income_parent = frappe.db.get_value("Account", {"account_name": f"Income - {company_abbr}", "company": company}, "name")
        
        if not income_parent:
            frappe.throw(f"No 'Income' group account found for {company}.")
            
        # Account properties
        props = {
            "account_type": "Income Account",
            "is_group": 1,
            "root_type": "Income"
        }
        
        # Create the parent account
        parent_doc = frappe.get_doc({
            "doctype": "Account",
            "account_name": parent_account_name.split(" - ")[0],  # Remove company suffix
            "company": company,
            "parent_account": income_parent,
            "is_group": props["is_group"],
            "account_type": props["account_type"],
            "report_type": "Profit and Loss",
            "root_type": props["root_type"]
        })
        parent_doc.insert(ignore_permissions=True)
        frappe.db.commit()


def get_account(company, account_type, member_id=None):
    """Return a valid account under SHG COA structure."""
    company_abbr = frappe.db.get_value("Company", company, "abbr")
    if not company_abbr:
        frappe.throw(f"Company abbreviation missing for {company}")

    # Define structured COA paths
    coa_map = {
        "members": f"SHG Members - {company_abbr}",
        "loans_receivable": f"SHG Loans receivable - {company_abbr}",
        "contributions": f"SHG Contributions - {company_abbr}",
        "income": f"SHG Income - {company_abbr}",
        "fines": f"SHG Fines - {company_abbr}"
    }

    # Ensure parent account exists
    parent = coa_map.get(account_type)
    if not frappe.db.exists("Account", {"account_name": parent, "company": company}):
        # Auto-create parent account if missing
        create_parent_account(company, account_type, parent)

    # For member-level accounts
    if member_id:
        child_name = f"{member_id} - {company_abbr}"
        # Check if account already exists to prevent duplicates
        existing_account = frappe.db.get_value("Account", {"account_name": child_name, "company": company})
        if existing_account:
            return existing_account
            
        # Create account if it doesn't exist
        try:
            child = frappe.get_doc({
                "doctype": "Account",
                "account_name": child_name,
                "parent_account": parent,
                "company": company,
                "account_type": "Receivable",
                "is_group": 0
            })
            child.insert(ignore_permissions=True)
            return child.name
        except frappe.DuplicateEntryError:
            # Handle race condition where account was created between check and insert
            frappe.clear_last_message()
            return frappe.db.get_value("Account", {"account_name": child_name, "company": company})
    
    return frappe.db.get_value("Account", {"account_name": parent, "company": company})

def get_or_create_account(company, account_name, parent, account_type, root_type):
    """
    Safely get or create an account with idempotent behavior.
    Checks for existing accounts before creating new ones.
    
    Args:
        company (str): Company name
        account_name (str): Account name to check/create
        parent (str): Parent account name
        account_type (str): Type of account
        root_type (str): Root type (Asset, Liability, Equity, Income, Expense)
        
    Returns:
        str: Name of existing or newly created account
    """
    # Normalize account name by removing company suffix if present
    company_abbr = frappe.db.get_value("Company", company, "abbr")
    base_account_name = account_name.split(" - ")[0] if " - " in account_name else account_name
    
    # Check for existing account with exact name
    existing = frappe.db.get_value("Account", {
        "account_name": account_name,
        "company": company
    })
    
    if existing:
        return existing
    
    # Also check for account with company suffix pattern
    if company_abbr:
        suffixed_name = f"{base_account_name} - {company_abbr}"
        if suffixed_name != account_name:
            existing_suffixed = frappe.db.get_value("Account", {
                "account_name": suffixed_name,
                "company": company
            })
            if existing_suffixed:
                return existing_suffixed
    
    # Create account if none exists
    try:
        account_doc = frappe.get_doc({
            "doctype": "Account",
            "company": company,
            "account_name": account_name,
            "parent_account": parent,
            "account_type": account_type,
            "root_type": root_type,
            "is_group": 0  # Always create as leaf node for posting
        })
        account_doc.insert(ignore_permissions=True)
        return account_doc.name
    except frappe.DuplicateEntryError:
        # Race condition protection
        frappe.clear_last_message()
        return frappe.db.get_value("Account", {
            "account_name": account_name,
            "company": company
        })
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"SHG - Account Creation Failed: {account_name}")
        frappe.throw(_(f"Failed to create account {account_name}: {str(e)}"))

def get_or_create_member_account(member, company):
    """
    Ensure each SHG Member has a personal ledger account under 'SHG Members - [Company Abbr]'.
    Auto-creates the parent and child accounts if missing.
    
    Args:
        member (SHGMember): The member document
        company (str): The company name
        
    Returns:
        str: The name of the member's account
    """
    return get_account(company, "members", member.name)

def get_or_create_shg_contributions_account(company):
    """
    Get or create the SHG Contributions account.
    
    Args:
        company (str): The company name
        
    Returns:
        str: The name of the contributions account
    """
    # Get company abbreviation
    company_abbr = frappe.get_value("Company", company, "abbr")
    
    # Get parent account using frappe.db.get_value for robustness
    income_parent = frappe.db.get_value("Account", {"account_name": "Income", "company": company}, "name")
    if not income_parent:
        income_parent = frappe.db.get_value("Account", {"account_name": f"Income - {company_abbr}", "company": company}, "name")
    
    # Check if account already exists to prevent duplicates
    existing_account = frappe.db.get_value("Account", {
        "account_name": "SHG Contributions",
        "company": company
    })
    if existing_account:
        return existing_account
    
    return get_or_create_account(
        company,
        "SHG Contributions",
        income_parent,
        "Income Account",
        "Income"
    )

def get_or_create_shg_loans_account(company):
    """
    Get or create the Loans Disbursed account.
    
    Args:
        company (str): The company name
        
    Returns:
        str: The name of the loans account
    """
    # Get company abbreviation
    company_abbr = frappe.get_value("Company", company, "abbr")
    
    # Get parent account using frappe.db.get_value for robustness
    loans_parent = frappe.db.get_value("Account", {"account_name": "Loans and Advances (Assets)", "company": company}, "name")
    if not loans_parent:
        loans_parent = frappe.db.get_value("Account", {"account_name": f"Loans and Advances (Assets) - {company_abbr}", "company": company}, "name")
    
    # Check if account already exists to prevent duplicates
    existing_account = frappe.db.get_value("Account", {
        "account_name": "Loans Disbursed",
        "company": company
    })
    if existing_account:
        return existing_account
    
    return get_or_create_account(
        company,
        "Loans Disbursed",
        loans_parent,
        "Receivable",
        "Asset"
    )

def get_or_create_shg_interest_income_account(company):
    """
    Get or create the SHG Interest Income account.
    
    Args:
        company (str): The company name
        
    Returns:
        str: The name of the interest income account
    """
    # Get company abbreviation
    company_abbr = frappe.get_value("Company", company, "abbr")
    
    # Get parent account using frappe.db.get_value for robustness
    income_parent = frappe.db.get_value("Account", {"account_name": "Income", "company": company}, "name")
    if not income_parent:
        income_parent = frappe.db.get_value("Account", {"account_name": f"Income - {company_abbr}", "company": company}, "name")
    
    # Check if account already exists to prevent duplicates
    existing_account = frappe.db.get_value("Account", {
        "account_name": "SHG Interest Income",
        "company": company
    })
    if existing_account:
        return existing_account
    
    return get_or_create_account(
        company,
        "SHG Interest Income",
        income_parent,
        "Income Account",
        "Income"
    )

def get_or_create_shg_penalty_income_account(company):
    """
    Get or create the SHG Penalty Income account.
    
    Args:
        company (str): The company name
        
    Returns:
        str: The name of the penalty income account
    """
    # Get company abbreviation
    company_abbr = frappe.get_value("Company", company, "abbr")
    
    # Get parent account using frappe.db.get_value for robustness
    income_parent = frappe.db.get_value("Account", {"account_name": "Income", "company": company}, "name")
    if not income_parent:
        income_parent = frappe.db.get_value("Account", {"account_name": f"Income - {company_abbr}", "company": company}, "name")
    
    # Check if account already exists to prevent duplicates
    existing_account = frappe.db.get_value("Account", {
        "account_name": "SHG Penalty Income",
        "company": company
    })
    if existing_account:
        return existing_account
    
    return get_or_create_account(
        company,
        "SHG Penalty Income",
        income_parent,
        "Income Account",
        "Income"
    )

def get_or_create_shg_parent_account(company):
    """
    Get or create the SHG Members parent account.
    
    Args:
        company (str): The company name
        
    Returns:
        str: The name of the parent account
    """
    # Get company abbreviation
    company_abbr = frappe.get_value("Company", company, "abbr")
    
    # Get parent account using frappe.db.get_value for robustness
    ar_parent = frappe.db.get_value("Account", {"account_name": "Accounts Receivable", "company": company}, "name")
    if not ar_parent:
        ar_parent = frappe.db.get_value("Account", {"account_name": f"Accounts Receivable - {company_abbr}", "company": company}, "name")
    
    # Check if account already exists to prevent duplicates
    existing_account = frappe.db.get_value("Account", {
        "account_name": "SHG Members",
        "company": company
    })
    if existing_account:
        return existing_account
    
    return get_or_create_account(
        company,
        "SHG Members",
        ar_parent,
        "Receivable",
        "Asset"
    )