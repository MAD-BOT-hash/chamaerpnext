import frappe
from frappe import _

def set_member_credit_account(doc, method):
    """
    Automatically map the Credit Account (or "Paid To" account) from the member's personal account
    that was created during member registration.
    
    Args:
        doc: Payment Entry document
        method: Method name (validate, on_submit, etc.)
    """
    try:
        # Check if this is a Receive payment type and party is set
        if doc.payment_type == "Receive" and doc.party_type == "Customer" and doc.party:
            # Get member ID from the customer
            member_id = frappe.db.get_value("Customer", doc.party, "member_id")
            if member_id:
                # Get SHG Settings
                settings = frappe.get_doc("SHG Settings")
                account_prefix = settings.default_account_prefix or "PFG"
                
                # Construct the account name
                account_name = f"{member_id} - {account_prefix}"
                
                # Check if the account exists
                member_account = frappe.db.exists("Account", account_name)
                if member_account:
                    # Set the paid_to account and make it read-only
                    doc.paid_to = member_account
                    # Note: Making fields read-only is typically done in the client-side JavaScript
                else:
                    # Account doesn't exist, check if auto-create is enabled
                    if settings.auto_create_missing_member_accounts:
                        # Create the member account
                        parent_ledger = settings.default_parent_ledger
                        if not parent_ledger:
                            frappe.throw(_("Default Parent Ledger is not set in SHG Settings"))
                        
                        # Create the account
                        account = frappe.new_doc("Account")
                        account.account_name = f"{member_id} - {account_prefix}"
                        account.account_number = member_id
                        account.account_type = "Receivable"
                        account.parent_account = parent_ledger
                        account.company = doc.company
                        account.is_group = 0
                        account.insert(ignore_permissions=True)
                        
                        # Set the paid_to account
                        doc.paid_to = account.name
                    else:
                        # Prompt user to create account
                        frappe.msgprint(_("No linked account found for this member. Please create one manually or enable auto-create in SHG Settings."))
                        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Set Member Credit Account Failed")
        # Don't throw error to avoid blocking the payment entry creation
        pass

def create_member_account(member_id, company, parent_ledger=None, account_prefix=None):
    """
    Create a member account in the Chart of Accounts.
    
    Args:
        member_id (str): Member ID
        company (str): Company name
        parent_ledger (str): Parent ledger account name
        account_prefix (str): Account prefix (default: PFG)
        
    Returns:
        str: Name of the created account
    """
    try:
        # Get SHG Settings if not provided
        if not parent_ledger or not account_prefix:
            settings = frappe.get_doc("SHG Settings")
            if not parent_ledger:
                parent_ledger = settings.default_parent_ledger
            if not account_prefix:
                account_prefix = settings.default_account_prefix or "PFG"
        
        if not parent_ledger:
            frappe.throw(_("Parent ledger is required to create member account"))
            
        # Construct the account name
        account_name = f"{member_id} - {account_prefix}"
        
        # Check if account already exists
        if frappe.db.exists("Account", account_name):
            return account_name
            
        # Create the account
        account = frappe.new_doc("Account")
        account.account_name = account_name
        account.account_number = member_id
        account.account_type = "Receivable"
        account.parent_account = parent_ledger
        account.company = company
        account.is_group = 0
        account.insert(ignore_permissions=True)
        
        return account.name
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Member Account Failed")
        frappe.throw(_("Failed to create member account: {0}").format(str(e)))