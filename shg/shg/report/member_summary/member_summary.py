import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("Member ID"),
            "fieldname": "member_id",
            "fieldtype": "Link",
            "options": "SHG Member",
            "width": 150
        },
        {
            "label": _("Member Name"),
            "fieldname": "member_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Membership Status"),
            "fieldname": "membership_status",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Total Contributions"),
            "fieldname": "total_contributions",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Total Loans Taken"),
            "fieldname": "total_loans_taken",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Current Loan Balance"),
            "fieldname": "current_loan_balance",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Credit Score"),
            "fieldname": "credit_score",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Last Contribution Date"),
            "fieldname": "last_contribution_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Last Loan Date"),
            "fieldname": "last_loan_date",
            "fieldtype": "Date",
            "width": 120
        }
    ]

def get_data(filters):
    conditions = ""
    if filters.get("membership_status"):
        conditions += " AND m.membership_status = %(membership_status)s"
        
    query = f"""
        SELECT 
            m.name as member_id,
            m.member_name,
            m.membership_status,
            m.total_contributions,
            m.total_loans_taken,
            m.current_loan_balance,
            m.credit_score,
            m.last_contribution_date,
            m.last_loan_date
        FROM `tabSHG Member` m
        WHERE m.docstatus = 1 {conditions}
        ORDER BY m.member_name
    """
    
    return frappe.db.sql(query, filters, as_dict=1)