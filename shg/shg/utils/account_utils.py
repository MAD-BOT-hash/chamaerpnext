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
    # Get company abbreviation
    company_abbr = frappe.get_value("Company", company, "abbr")
    if not company_abbr:
        frappe.throw(f"Company abbreviation not found for {company}")
    
    # Ensure account number is set
    if not member.account_number:
        member.set_account_number()
        member.save()
    
    # --- Get the Accounts Receivable parent ---
    accounts_receivable = frappe.db.get_value(
        "Account",
        {"account_type": "Receivable", "is_group": 1, "company": company},
        "name"
    )
    if not accounts_receivable:
        frappe.throw(f"No 'Accounts Receivable' group account found for {company}.")

    # --- Ensure SHG Members parent account exists ---
    parent_account_name = f"SHG Members - {company_abbr}"
    parent_account = frappe.db.get_value(
        "Account",
        {"account_name": parent_account_name, "company": company},
        "name"
    )

    if not parent_account:
        # Create parent group account automatically
        parent_doc = frappe.get_doc({
            "doctype": "Account",
            "account_name": parent_account_name,
            "company": company,
            "parent_account": accounts_receivable,
            "is_group": 1,
            "account_type": "Receivable",
            "report_type": "Balance Sheet",
            "root_type": "Asset"
        })
        parent_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        parent_account = parent_doc.name
        frappe.msgprint(f"✅ Created parent account '{parent_account_name}' under Accounts Receivable.")

    # --- Check if the member already has an account ---
    member_account_name = f"{member.account_number} - {company_abbr}"
    member_account = frappe.db.exists("Account", {"account_name": member_account_name, "company": company})

    # --- Create child account if not exists ---
    if not member_account:
        member_doc = frappe.get_doc({
            "doctype": "Account",
            "account_name": member_account_name,
            "company": company,
            "parent_account": parent_account,
            "is_group": 0,
            "account_type": "Receivable",
            "report_type": "Balance Sheet",
            "root_type": "Asset"
        })
        member_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        member_account = member_doc.name
        frappe.msgprint(f"✅ Created member account '{member_account_name}' under '{parent_account_name}'.")

    return member_account

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