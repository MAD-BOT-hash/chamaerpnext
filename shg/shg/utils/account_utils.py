import frappe
from frappe import _

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
        frappe.throw(f"Parent account '{parent}' not found. Please create it under Accounts Receivable.")

    # For member-level accounts
    if member_id:
        child_name = f"{member_id} - {company_abbr}"
        if not frappe.db.exists("Account", {"account_name": child_name, "company": company}):
            child = frappe.get_doc({
                "doctype": "Account",
                "account_name": child_name,
                "parent_account": parent,
                "company": company,
                "account_type": "Receivable",
                "is_group": 0
            })
            child.insert(ignore_permissions=True)
        return frappe.db.get_value("Account", {"account_name": child_name, "company": company})
    
    return frappe.db.get_value("Account", {"account_name": parent, "company": company})

def get_or_create_account(account_name, company, parent_account=None, account_type=None, is_group=0, root_type=None):
    """
    Get an account by name, trying both plain name and company-suffixed name.
    If not found, create it under the specified parent account.
    
    Args:
        account_name (str): The base account name (e.g., "SHG Contributions")
        company (str): The company name
        parent_account (str): The parent account to create under if account doesn't exist
        account_type (str): The account type for creation
        is_group (int): Whether the account is a group account
        root_type (str): The root type for the account (Asset, Liability, Equity, Income, Expense)
        
    Returns:
        str: The name of the found or created account
    """
    # Get company abbreviation
    company_abbr = frappe.get_value("Company", company, "abbr")
    
    # First, try to find the account with the plain name
    account = frappe.db.get_value("Account", {"account_name": account_name, "company": company})
    
    # If not found, try with company suffix (using abbreviation)
    if not account:
        suffixed_name = f"{account_name} - {company_abbr}"
        account = frappe.db.get_value("Account", {"account_name": suffixed_name, "company": company})
    
    # If still not found, create it
    if not account:
        try:
            account_doc = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": account_name,
                "parent_account": parent_account,
                "account_type": account_type,
                "is_group": is_group,
                "root_type": root_type
            })
            account_doc.insert()
            account = account_doc.name
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"SHG - Account Creation Failed: {account_name}")
            frappe.throw(_(f"Failed to create account {account_name}: {str(e)}"))
    
    return account

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
    
    return get_or_create_account(
        "SHG Contributions",
        company,
        parent_account=income_parent,
        account_type="Income Account",
        is_group=0,
        root_type="Income"
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
    
    return get_or_create_account(
        "Loans Disbursed",
        company,
        parent_account=loans_parent,
        account_type="Receivable",
        is_group=0,
        root_type="Asset"
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
    
    return get_or_create_account(
        "SHG Interest Income",
        company,
        parent_account=income_parent,
        account_type="Income Account",
        is_group=0,
        root_type="Income"
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
    
    return get_or_create_account(
        "SHG Penalty Income",
        company,
        parent_account=income_parent,
        account_type="Income Account",
        is_group=0,
        root_type="Income"
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
    
    return get_or_create_account(
        "SHG Members",
        company,
        parent_account=ar_parent,
        account_type="Receivable",
        is_group=1,
        root_type="Asset"
    )