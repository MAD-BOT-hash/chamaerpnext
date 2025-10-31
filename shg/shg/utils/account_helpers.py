import frappe

def get_or_create_member_receivable(member_id, company):
    """Return or create a member-specific receivable subaccount under SHG Loans receivable - <abbr>."""
    if not member_id:
        frappe.throw("Member ID is required to get or create receivable account.")

    # --- Get company abbreviation ---
    abbr = frappe.db.get_value("Company", company, "abbr")
    if not abbr:
        frappe.throw(f"Company abbreviation not found for {company}")

    parent_account = f"SHG Loans receivable - {abbr}"

    # --- Ensure parent account exists and is_group = 1 ---
    if not frappe.db.exists("Account", parent_account):
        frappe.throw(f"Parent account {parent_account} missing. Please create it under Accounts Receivable - {abbr}.")
    
    frappe.db.set_value("Account", parent_account, "is_group", 1)

    # --- Get member info ---
    member_name = frappe.db.get_value("SHG Member", member_id, "member_name") or member_id
    account_name = f"{member_name.strip().upper()} - {abbr}"

    # --- If subaccount missing, create it ---
    if not frappe.db.exists("Account", account_name):
        acc = frappe.get_doc({
            "doctype": "Account",
            "account_name": member_name.strip().upper(),
            "parent_account": parent_account,
            "company": company,
            "is_group": 0,
            "account_type": "Receivable",
            "root_type": "Asset",
        })
        acc.insert(ignore_permissions=True)
        frappe.db.commit()

    # --- ✅ Always return the child account ---
    return account_name