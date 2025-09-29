import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def after_install():
    """Setup after installing SHG app"""
    create_custom_fields_for_existing_doctypes()
    create_default_accounts()
    create_default_settings()
    setup_user_roles()
    # Register workspace components
    register_workspace_components()

def create_custom_fields_for_existing_doctypes():
    """Add custom fields to existing ERPNext doctypes"""
    custom_fields = {
        "Customer": [
            {
                "fieldname": "is_shg_member",
                "label": "Is SHG Member",
                "fieldtype": "Check",
                "insert_after": "customer_type"
            },
            {
                "fieldname": "shg_member_id", 
                "label": "SHG Member ID",
                "fieldtype": "Data",
                "insert_after": "is_shg_member",
                "depends_on": "is_shg_member"
            }
        ]
    }
    create_custom_fields(custom_fields, update=True)

def create_default_accounts():
    """Create default GL accounts for SHG operations"""
    company = frappe.defaults.get_user_default("Company")
    if not company:
        companies = frappe.get_all("Company", limit=1)
        if companies:
            company = companies[0].name
        else:
            frappe.throw("No company found. Please create a company first.")
    
    accounts_to_create = [
        {
            "account_name": "SHG Members",
            "parent_account": f"Accounts Receivable - {company}",
            "account_type": "Receivable",
            "is_group": 1
        },
        {
            "account_name": "SHG Contributions",
            "parent_account": f"Income - {company}",
            "account_type": "Income Account",
            "is_group": 0
        },
        {
            "account_name": "SHG Interest Income",
            "parent_account": f"Income - {company}",
            "account_type": "Income Account", 
            "is_group": 0
        },
        {
            "account_name": "SHG Penalty Income",
            "parent_account": f"Income - {company}",
            "account_type": "Income Account",
            "is_group": 0
        }
    ]
    
    for account_data in accounts_to_create:
        account_name = f"{account_data['account_name']} - {company}"
        if not frappe.db.exists("Account", account_name):
            try:
                account = frappe.get_doc({
                    "doctype": "Account",
                    "company": company,
                    "account_name": account_data["account_name"],
                    "parent_account": account_data["parent_account"],
                    "account_type": account_data.get("account_type"),
                    "is_group": account_data["is_group"]
                })
                account.insert()
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), "SHG Install - Account Creation Failed")

def create_default_settings():
    """Create default SHG settings"""
    if not frappe.db.exists("SHG Settings", "SHG Settings"):
        try:
            settings = frappe.get_doc({
                "doctype": "SHG Settings",
                "default_contribution_amount": 500,
                "contribution_frequency": "Weekly",
                "allow_voluntary_contributions": 1,
                "default_interest_rate": 12,
                "interest_calculation_method": "Reducing Balance",
                "penalty_rate": 5,
                "meeting_frequency": "Weekly",
                "absentee_fine": 50,
                "lateness_fine": 20,
                "meeting_quorum_percentage": 60,
                "currency": "KES"
            })
            settings.insert()
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Install - Settings Creation Failed")

def setup_user_roles():
    """Setup default user roles for SHG"""
    roles_to_create = ["SHG Admin", "SHG Treasurer", "SHG Member", "SHG Auditor"]
    
    for role_name in roles_to_create:
        if not frappe.db.exists("Role", role_name):
            try:
                role = frappe.get_doc({
                    "doctype": "Role",
                    "role_name": role_name,
                    "desk_access": 1
                })
                role.insert()
                frappe.db.commit()
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"SHG Install - Role Creation Failed: {role_name}")

def register_workspace_components():
    """Register workspace components during installation"""
    # This function ensures all workspace components are properly registered
    try:
        # Import all workspace components to ensure they're registered
        from shg.shg.workspace import shg
        from shg.shg.workspace.card import member_management, financial_management, meeting_management, reports_analytics, settings
        from shg.shg.number_card import active_members, monthly_contributions, outstanding_loans, upcoming_meetings
        from shg.shg.dashboard_chart import members_overview, financial_summary
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG Install - Workspace Component Registration Failed")

# Hook functions
def validate_member(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()

def create_member_ledger(doc, method):
    """Hook function called from hooks.py"""
    doc.create_customer_link()
    doc.create_member_ledger()