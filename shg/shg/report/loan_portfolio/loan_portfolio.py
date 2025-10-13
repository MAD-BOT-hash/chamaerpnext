import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("Loan ID"),
            "fieldname": "loan_id",
            "fieldtype": "Link",
            "options": "SHG Loan",
            "width": 150
        },
        {
            "label": _("Member"),
            "fieldname": "member",
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
            "label": _("Loan Amount"),
            "fieldname": "loan_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Paid to Date"),
            "fieldname": "paid_to_date",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Outstanding"),
            "fieldname": "outstanding",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Overdue"),
            "fieldname": "overdue",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Interest Rate (%)"),
            "fieldname": "interest_rate",
            "fieldtype": "Percent",
            "width": 100
        },
        {
            "label": _("Loan Period (Months)"),
            "fieldname": "loan_period_months",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Disbursement Date"),
            "fieldname": "disbursement_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Next Due Date"),
            "fieldname": "next_due_date",
            "fieldtype": "Date",
            "width": 120
        }
    ]

def get_data(filters):
    conditions = ""
    if filters.get("status"):
        conditions += " AND l.status = %(status)s"
        
    query = f"""
        SELECT 
            l.name as loan_id,
            l.member,
            l.member_name,
            l.loan_amount,
            (l.loan_amount - l.balance_amount) as paid_to_date,
            l.balance_amount as outstanding,
            CASE 
                WHEN l.next_due_date < CURDATE() AND l.balance_amount > 0 THEN l.balance_amount
                ELSE 0
            END as overdue,
            l.interest_rate,
            l.loan_period_months,
            l.status,
            l.disbursement_date,
            l.next_due_date
        FROM `tabSHG Loan` l
        WHERE l.docstatus = 1 {conditions}
        ORDER BY l.disbursement_date DESC
    """
    
    return frappe.db.sql(query, filters, as_dict=1)