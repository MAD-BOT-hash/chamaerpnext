import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def after_install():
    """Setup after installing SHG app"""
    create_custom_fields_for_existing_doctypes()
    create_default_accounts()
    create_default_settings()
    setup_user_roles()
    
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
            
    def update_financial_summary(self):
        """Update member's financial summary"""
        # Calculate total contributions
        total_contributions = frappe.db.sql("""
            SELECT SUM(amount) FROM `tabSHG Contribution` 
            WHERE member = %s AND docstatus = 1
        """, self.name)[0][0] or 0
        
        # Calculate total loans taken
        total_loans = frappe.db.sql("""
            SELECT SUM(loan_amount) FROM `tabSHG Loan` 
            WHERE member = %s AND docstatus = 1
        """, self.name)[0][0] or 0
        
        # Calculate current loan balance
        current_balance = frappe.db.sql("""
            SELECT SUM(balance_amount) FROM `tabSHG Loan` 
            WHERE member = %s AND status = 'Disbursed'
        """, self.name)[0][0] or 0
        
        # Update fields
        frappe.db.set_value("SHG Member", self.name, {
            "total_contributions": total_contributions,
            "total_loans_taken": total_loans,
            "current_loan_balance": current_balance
        })

# Hook functions
def validate_member(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()

def create_member_ledger(doc, method):
    """Hook function called from hooks.py"""
    doc.create_customer_link()
    doc.create_member_ledger()