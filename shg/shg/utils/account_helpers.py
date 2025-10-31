import frappe
from frappe.utils import flt

def get_or_create_member_receivable(member_id, company):
    abbr = frappe.db.get_value("Company", company, "abbr")
    parent = f"SHG Loans receivable - {abbr}"

    if not frappe.db.exists("Account", parent):
        frappe.throw(f"Parent account {parent} missing. Please create it under Accounts Receivable.")

    member_name = frappe.db.get_value("SHG Member", member_id, "member_name") or member_id
    sub_name = f"{member_id} - {abbr}"

    if not frappe.db.exists("Account", sub_name):
        frappe.get_doc({
            "doctype": "Account",
            "account_name": member_name,
            "name": sub_name,
            "parent_account": parent,
            "company": company,
            "is_group": 0,
            "account_type": "Receivable"
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    return sub_name