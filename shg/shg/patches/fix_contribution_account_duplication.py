import frappe
from frappe import _
from shg.shg.utils.account_utils import get_or_create_account

def execute():
    """
    Patch to fix duplicate SHG Contribution accounts and repair GL references.
    
    This patch will:
    1. Identify and remove duplicate SHG Contribution accounts
    2. Re-link GL entries to the correct accounts
    3. Ensure only one SHG Contributions account exists per company
    """
    frappe.logger().info("Starting SHG Contribution Account Duplication Fix Patch")
    
    # Get all companies
    companies = frappe.get_all("Company", fields=["name", "abbr"])
    
    for company_doc in companies:
        company = company_doc.name
        company_abbr = company_doc.abbr
        frappe.logger().info(f"Processing company: {company}")
        
        try:
            # Find all SHG Contribution accounts for this company
            contribution_accounts = frappe.get_all("Account", 
                filters={
                    "company": company,
                    "account_name": ["like", "%SHG Contributions%"]
                },
                fields=["name", "account_name"]
            )
            
            if not contribution_accounts:
                frappe.logger().info(f"No SHG Contribution accounts found for company {company}")
                continue
                
            # Identify the correct account (preferably with company suffix)
            correct_account = None
            duplicate_accounts = []
            
            for account in contribution_accounts:
                if account.account_name == f"SHG Contributions - {company_abbr}":
                    correct_account = account.name
                else:
                    duplicate_accounts.append(account.name)
            
            # If we don't have the properly suffixed account, pick the first one as correct
            if not correct_account and contribution_accounts:
                correct_account = contribution_accounts[0].name
                duplicate_accounts = [acc.name for acc in contribution_accounts[1:]]
            
            frappe.logger().info(f"Correct account: {correct_account}")
            frappe.logger().info(f"Duplicate accounts to remove: {duplicate_accounts}")
            
            # Process duplicates
            for duplicate in duplicate_accounts:
                # Re-link GL entries to the correct account
                frappe.db.sql("""
                    UPDATE `tabGL Entry`
                    SET account = %s
                    WHERE account = %s
                """, (correct_account, duplicate))
                
                # Re-link Journal Entry accounts
                frappe.db.sql("""
                    UPDATE `tabJournal Entry Account`
                    SET account = %s
                    WHERE account = %s
                """, (correct_account, duplicate))
                
                # Re-link Payment Entry accounts
                frappe.db.sql("""
                    UPDATE `tabPayment Entry`
                    SET paid_to = %s
                    WHERE paid_to = %s
                """, (correct_account, duplicate))
                
                frappe.db.sql("""
                    UPDATE `tabPayment Entry`
                    SET paid_from = %s
                    WHERE paid_from = %s
                """, (correct_account, duplicate))
                
                # Delete the duplicate account
                frappe.delete_doc("Account", duplicate, ignore_missing=True)
                frappe.logger().info(f"Removed duplicate account: {duplicate}")
            
            # Ensure parent income account exists
            income_parent = frappe.db.get_value("Account", {"account_name": "Income", "company": company}, "name")
            if not income_parent:
                income_parent = frappe.db.get_value("Account", {"account_name": f"Income - {company_abbr}", "company": company}, "name")
            
            # Ensure the correct SHG Contributions account is properly configured
            if correct_account:
                # Update the account to ensure it has correct properties
                account_doc = frappe.get_doc("Account", correct_account)
                account_doc.account_type = "Income Account"
                account_doc.root_type = "Income"
                account_doc.parent_account = income_parent
                account_doc.is_group = 0
                account_doc.save()
                frappe.logger().info(f"Updated account properties for: {correct_account}")
            
            frappe.db.commit()
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to fix contribution accounts for company {company}")
            frappe.logger().error(f"Error processing company {company}: {str(e)}")
            frappe.db.rollback()
    
    frappe.logger().info("Completed SHG Contribution Account Duplication Fix Patch")