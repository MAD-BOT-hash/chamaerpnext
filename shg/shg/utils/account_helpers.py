import frappe

def get_or_create_member_receivable(member_id, company):
    """Ensure a per-member receivable account exists under SHG Loans receivable - <abbr>."""
    abbr = frappe.db.get_value("Company", company, "abbr")
    parent_name = f"SHG Loans receivable - {abbr}"

    # Verify parent exists and is a group
    if not frappe.db.exists("Account", parent_name):
        frappe.throw(f"Parent account {parent_name} missing. Please create it under Accounts Receivable.")
    if not frappe.db.get_value("Account", parent_name, "is_group"):
        frappe.throw(f"{parent_name} must be marked as Group = Yes.")

    # Construct subaccount name
    member_name = frappe.db.get_value("SHG Member", member_id, "member_name") or member_id
    child_name = f"{member_name.upper()} - {abbr}"

    # Create if missing
    if not frappe.db.exists("Account", child_name):
        frappe.get_doc({
            "doctype": "Account",
            "account_name": member_name.upper(),
            "name": child_name,
            "parent_account": parent_name,
            "company": company,
            "is_group": 0,
            "account_type": "Receivable",
            "root_type": "Asset"
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    return child_name