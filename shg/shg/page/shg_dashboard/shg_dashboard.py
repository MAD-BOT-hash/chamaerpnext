import frappe
from frappe import _

def has_website_permission(doc, ptype, user, verbose=False):
    """Check if user has permission to view the dashboard"""
    # Allow all users with SHG roles to view the dashboard
    shg_roles = ["SHG Admin", "SHG Treasurer", "SHG Member", "SHG Auditor"]
    user_roles = frappe.get_roles(user)
    
    # Check if user has any SHG role
    if any(role in shg_roles for role in user_roles):
        return True
    
    return False

def get_context(context):
    """Pass context to the page"""
    context.no_cache = 1

@frappe.whitelist()
def get_dashboard_data():
    """Get data for the dashboard charts"""
    # Get total active members
    active_members = frappe.db.count("SHG Member", filters={"membership_status": "Active"})
    
    # Get total contributions
    total_contributions = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0) 
        FROM `tabSHG Contribution` 
        WHERE docstatus = 1
    """)[0][0]
    
    # Get active loans and outstanding balance
    active_loans = frappe.db.count("SHG Loan", filters={"status": "Disbursed"})
    outstanding_balance = frappe.db.sql("""
        SELECT COALESCE(SUM(balance_amount), 0) 
        FROM `tabSHG Loan` 
        WHERE status = 'Disbursed'
    """)[0][0]
    
    return {
        "active_members": active_members,
        "total_contributions": float(total_contributions),
        "active_loans": active_loans,
        "outstanding_balance": float(outstanding_balance)
    }