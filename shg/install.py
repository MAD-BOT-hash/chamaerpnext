import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def after_install():
    """Setup after installing SHG app"""
    create_custom_fields_for_existing_doctypes()
    create_default_accounts()
    create_default_settings()
    setup_user_roles()
    create_default_loan_types()
    create_default_contribution_types()
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
    
    # Create parent account for SHG Members
    parent_account_name = f"SHG Members - {company}"
    if not frappe.db.exists("Account", parent_account_name):
        try:
            parent_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "SHG Members",
                "parent_account": f"Accounts Receivable - {company}",
                "account_type": "Receivable",
                "is_group": 1,
                "root_type": "Asset"
            })
            parent_account.insert()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Install - Parent Account Creation Failed")
    
    accounts_to_create = [
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
        },
        {
            "account_name": "Loans Disbursed",
            "parent_account": f"Loans and Advances (Assets) - {company}",
            "account_type": "Bank",
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
                    "is_group": account_data["is_group"],
                    "root_type": "Income" if account_data.get("account_type") == "Income Account" else "Asset"
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

def create_default_loan_types():
    """Create default loan types"""
    # Emergency Loan
    if not frappe.db.exists("SHG Loan Type", "Emergency Loan"):
        try:
            emergency_loan = frappe.get_doc({
                "doctype": "SHG Loan Type",
                "loan_type_name": "Emergency Loan",
                "description": "Short-term emergency loan for urgent needs",
                "interest_rate": 15,
                "interest_type": "Reducing Balance",
                "default_tenure_months": 6,
                "penalty_rate": 10,
                "repayment_frequency": "Monthly",
                "minimum_amount": 1000,
                "maximum_amount": 50000,
                "enabled": 1
            })
            emergency_loan.insert()
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Install - Emergency Loan Creation Failed")
    
    # Development Loan
    if not frappe.db.exists("SHG Loan Type", "Development Loan"):
        try:
            development_loan = frappe.get_doc({
                "doctype": "SHG Loan Type",
                "loan_type_name": "Development Loan",
                "description": "Long-term development loan for business or personal development",
                "interest_rate": 12,
                "interest_type": "Reducing Balance",
                "default_tenure_months": 12,
                "penalty_rate": 8,
                "repayment_frequency": "Monthly",
                "minimum_amount": 5000,
                "maximum_amount": 200000,
                "enabled": 1
            })
            development_loan.insert()
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Install - Development Loan Creation Failed")

def create_default_contribution_types():
    """Create default contribution types"""
    # Monthly Contribution
    if not frappe.db.exists("SHG Contribution Type", "Monthly Contribution"):
        try:
            monthly_contrib = frappe.get_doc({
                "doctype": "SHG Contribution Type",
                "contribution_type_name": "Monthly Contribution",
                "description": "Regular monthly contribution from members",
                "default_amount": 500,
                "frequency": "Monthly",
                "enabled": 1
            })
            monthly_contrib.insert()
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Install - Monthly Contribution Creation Failed")
    
    # Welfare Contribution
    if not frappe.db.exists("SHG Contribution Type", "Welfare Contribution"):
        try:
            welfare_contrib = frappe.get_doc({
                "doctype": "SHG Contribution Type",
                "contribution_type_name": "Welfare Contribution",
                "description": "Special contribution for welfare purposes",
                "default_amount": 1000,
                "frequency": "Monthly",
                "enabled": 1
            })
            welfare_contrib.insert()
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Install - Welfare Contribution Creation Failed")
    
    # Bi-Monthly Contribution
    if not frappe.db.exists("SHG Contribution Type", "Bi-Monthly Contribution"):
        try:
            bimonthly_contrib = frappe.get_doc({
                "doctype": "SHG Contribution Type",
                "contribution_type_name": "Bi-Monthly Contribution",
                "description": "Contribution collected every two months",
                "default_amount": 1000,
                "frequency": "Bi-Monthly",
                "enabled": 1
            })
            bimonthly_contrib.insert()
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Install - Bi-Monthly Contribution Creation Failed")

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
        from shg.shg.number_card import active_members, monthly_contributions, outstanding_loans, upcoming_meetings, bimonthly_contributions, loan_repayments, mpesa_payments
        from shg.shg.dashboard_chart import members_overview, financial_summary, mpesa_payments, loan_types, contribution_types
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG Install - Workspace Component Registration Failed")

def create_accounts_for_company(company):
    """Create default accounts for a specific company"""
    # Create parent account for SHG Members
    parent_account_name = f"SHG Members - {company}"
    if not frappe.db.exists("Account", parent_account_name):
        try:
            parent_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "SHG Members",
                "parent_account": f"Accounts Receivable - {company}",
                "account_type": "Receivable",
                "is_group": 1,
                "root_type": "Asset"
            })
            parent_account.insert()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"SHG - Parent Account Creation Failed for {company}")
    
    accounts_to_create = [
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
        },
        {
            "account_name": "Loans Disbursed",
            "parent_account": f"Loans and Advances (Assets) - {company}",
            "account_type": "Bank",
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
                    "is_group": account_data["is_group"],
                    "root_type": "Income" if account_data.get("account_type") == "Income Account" else "Asset"
                })
                account.insert()
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"SHG - Account Creation Failed for {company}: {account_data['account_name']}")

# Hook functions
def validate_member(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()

def create_member_ledger(doc, method):
    """Hook function called from hooks.py"""
    doc.create_customer_link()
    doc.create_member_ledger()