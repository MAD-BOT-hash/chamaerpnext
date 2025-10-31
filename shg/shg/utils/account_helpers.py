import frappe

def get_or_create_member_receivable(member_id, company):
    """Always return a member's leaf receivable account under SHG Loans receivable - <abbr>."""
    abbr = frappe.db.get_value("Company", company, "abbr")
    parent_account = f"SHG Loans receivable - {abbr}"

    # Ensure parent exists and is_group = 1
    if not frappe.db.exists("Account", parent_account):
        frappe.throw(f"Parent account {parent_account} missing. Please create it under Accounts Receivable.")
    is_group = frappe.db.get_value("Account", parent_account, "is_group")
    if not is_group:
        frappe.throw(f"Parent account {parent_account} must be marked as Group = Yes.")

    # Build member subaccount name
    member_name = frappe.db.get_value("SHG Member", member_id, "member_name") or member_id
    account_name = f"{member_name.upper()} - {abbr}"

    # Create if not exists
    if not frappe.db.exists("Account", account_name):
        account = frappe.get_doc({
            "doctype": "Account",
            "account_name": member_name.upper(),
            "name": account_name,
            "parent_account": parent_account,
            "company": company,
            "is_group": 0,
            "account_type": "Receivable",
            "root_type": "Asset"
        })
        account.insert(ignore_permissions=True)
        frappe.db.commit()

    # ✅ Always return the child account (leaf)
    return account_name