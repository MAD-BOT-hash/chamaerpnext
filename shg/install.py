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
    create_default_customer_groups()  # Add this line
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
    
    # Create all SHG accounts at once
    create_shg_accounts(company)

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

def create_default_customer_groups():
    """Create default customer groups for SHG"""
    # Create SHG Members customer group
    if not frappe.db.exists("Customer Group", "SHG Members"):
        try:
            customer_group = frappe.get_doc({
                "doctype": "Customer Group",
                "customer_group_name": "SHG Members",
                "parent_customer_group": "All Customer Groups",
                "is_group": 0
            })
            customer_group.insert()
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Install - Customer Group Creation Failed")

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

def create_shg_accounts(company):
    """Create all SHG-specific accounts at once"""
    company_abbr = frappe.get_value("Company", company, "abbr")

    # Ensure SHG Members group account exists
    parent_account_name = f"SHG Members - {company_abbr}"
    if not frappe.db.exists("Account", parent_account_name):
        try:
            # Get parent account using frappe.db.get_value for robustness
            ar_parent = frappe.db.get_value("Account", {"account_name": "Accounts Receivable", "company": company}, "name")
            if not ar_parent:
                ar_parent = frappe.db.get_value("Account", {"account_name": f"Accounts Receivable - {company_abbr}", "company": company}, "name")
            
            parent_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "SHG Members",
                "parent_account": ar_parent,
                "account_type": "Receivable",
                "is_group": 1,
                "root_type": "Asset"
            })
            parent_account.insert()
        except Exception:
            frappe.log_error(frappe.get_traceback(), "SHG Install - Parent Account Creation Failed")

    # Common parent accounts
    income_parent = frappe.db.get_value("Account", {"account_name": "Income", "company": company}, "name")
    if not income_parent:
        income_parent = frappe.db.get_value("Account", {"account_name": f"Income - {company_abbr}", "company": company}, "name")
    
    loans_parent = frappe.db.get_value("Account", {"account_name": "Loans and Advances (Assets)", "company": company}, "name")
    if not loans_parent:
        loans_parent = frappe.db.get_value("Account", {"account_name": f"Loans and Advances (Assets) - {company_abbr}", "company": company}, "name")

    accounts_to_create = [
        {
            "account_name": "SHG Contributions",
            "parent_account": income_parent,
            "is_group": 0,
            "root_type": "Income"
        },
        {
            "account_name": "SHG Interest Income",
            "parent_account": income_parent,
            "is_group": 0,
            "root_type": "Income"
        },
        {
            "account_name": "SHG Penalty Income",
            "parent_account": income_parent,
            "is_group": 0,
            "root_type": "Income"
        },
        {
            "account_name": "Loans Disbursed",
            "parent_account": loans_parent,
            "is_group": 0,
            "root_type": "Asset",
            "account_type": "Receivable"
        }
    ]

    for acc in accounts_to_create:
        account_name = f"{acc['account_name']} - {company_abbr}"
        if not frappe.db.exists("Account", account_name):
            try:
                account = frappe.get_doc({
                    "doctype": "Account",
                    "company": company,
                    "account_name": acc["account_name"],
                    "parent_account": acc["parent_account"],
                    "is_group": acc["is_group"],
                    "root_type": acc["root_type"],
                    "account_type": acc.get("account_type")
                })
                account.insert()
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"SHG Install - Account Creation Failed: {acc['account_name']}")

def create_accounts_for_company(company):
    """Create default accounts for a specific company"""
    # Create all SHG accounts at once
    create_shg_accounts(company)

# Hook functions
def validate_member(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()

def create_member_ledger(doc, method):
    """Hook function called from hooks.py"""
    doc.create_member_ledger_account()