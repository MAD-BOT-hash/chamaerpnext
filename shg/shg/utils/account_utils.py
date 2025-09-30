import frappe
from frappe import _

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
    # First, try to find the account with the plain name
    account = frappe.db.get_value("Account", {"account_name": account_name, "company": company})
    
    # If not found, try with company suffix
    if not account:
        suffixed_name = f"{account_name} - {company}"
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
    Get or create a member's ledger account.
    
    Args:
        member (SHGMember): The member document
        company (str): The company name
        
    Returns:
        str: The name of the member's account
    """
    # Ensure account number is set
    if not member.account_number:
        member.set_account_number()
        member.save()
    
    # Try to get existing account using member's account number with both plain and suffixed names
    account = frappe.db.get_value("Account", {"account_name": member.account_number, "company": company})
    
    if not account:
        suffixed_name = f"{member.account_number} - {company}"
        account = frappe.db.get_value("Account", {"account_name": suffixed_name, "company": company})
    
    # If account doesn't exist, create it
    if not account:
        try:
            # Get or create parent account
            parent_account = get_or_create_shg_parent_account(company)
            
            account_doc = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": member.account_number,
                "parent_account": parent_account,
                "account_type": "Receivable",
                "is_group": 0,
                "root_type": "Asset"
            })
            account_doc.insert()
            account = account_doc.name
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG - Member Account Creation Failed")
            frappe.throw(_(f"Failed to create member account: {str(e)}"))
    
    return account

def get_or_create_shg_contributions_account(company):
    """
    Get or create the SHG Contributions account.
    
    Args:
        company (str): The company name
        
    Returns:
        str: The name of the contributions account
    """
    return get_or_create_account(
        "SHG Contributions",
        company,
        parent_account=get_income_account(company),
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
    return get_or_create_account(
        "Loans Disbursed",
        company,
        parent_account=get_loans_and_advances_account(company),
        account_type="Bank",
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
    return get_or_create_account(
        "SHG Interest Income",
        company,
        parent_account=get_income_account(company),
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
    return get_or_create_account(
        "SHG Penalty Income",
        company,
        parent_account=get_income_account(company),
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
    return get_or_create_account(
        "SHG Members",
        company,
        parent_account=get_accounts_receivable_account(company),
        account_type="Receivable",
        is_group=1,
        root_type="Asset"
    )

def get_income_account(company):
    """Get the Income account for the company"""
    income_account = frappe.db.get_value("Account", {"account_name": "Income", "company": company})
    if not income_account:
        income_account = frappe.db.get_value("Account", {"account_name": f"Income - {company}", "company": company})
    return income_account

def get_accounts_receivable_account(company):
    """Get the Accounts Receivable account for the company"""
    ar_account = frappe.db.get_value("Account", {"account_name": "Accounts Receivable", "company": company})
    if not ar_account:
        ar_account = frappe.db.get_value("Account", {"account_name": f"Accounts Receivable - {company}", "company": company})
    return ar_account

def get_loans_and_advances_account(company):
    """Get the Loans and Advances account for the company"""
    la_account = frappe.db.get_value("Account", {"account_name": "Loans and Advances (Assets)", "company": company})
    if not la_account:
        la_account = frappe.db.get_value("Account", {"account_name": f"Loans and Advances (Assets) - {company}", "company": company})
    return la_account