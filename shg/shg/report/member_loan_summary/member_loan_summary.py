import frappe
from frappe import _
from frappe.utils import getdate, today

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("Member"),
            "fieldname": "member_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Loan ID"),
            "fieldname": "loan_id",
            "fieldtype": "Link",
            "options": "SHG Loan",
            "width": 150
        },
        {
            "label": _("Disbursement Date"),
            "fieldname": "disbursement_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Loan Amount"),
            "fieldname": "loan_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Total Payable"),
            "fieldname": "total_payable",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Total Paid"),
            "fieldname": "total_paid",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Outstanding Balance"),
            "fieldname": "outstanding_balance",
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
            "label": _("Next Due Date"),
            "fieldname": "next_due_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Days Overdue"),
            "fieldname": "days_overdue",
            "fieldtype": "Int",
            "width": 100
        }
    ]

def get_data(filters):
    conditions = ""
    params = {"today": getdate(today())}
    
    if filters.get("member"):
        conditions += " AND l.member = %(member)s"
        params["member"] = filters.get("member")
        
    if filters.get("loan"):
        conditions += " AND l.name = %(loan)s"
        params["loan"] = filters.get("loan")
        
    if filters.get("status"):
        conditions += " AND l.status = %(status)s"
        params["status"] = filters.get("status")
        
    query = f"""
        SELECT 
            l.member_name,
            l.name as loan_id,
            l.disbursement_date,
            l.loan_amount,
            l.total_payable,
            l.total_repaid as total_paid,
            l.balance_amount as outstanding_balance,
            l.interest_rate,
            l.loan_period_months,
            l.status,
            l.next_due_date,
            CASE 
                WHEN l.next_due_date < %(today)s THEN DATEDIFF(%(today)s, l.next_due_date)
                ELSE 0
            END as days_overdue
        FROM `tabSHG Loan` l
        WHERE l.docstatus = 1 {conditions}
        ORDER BY l.disbursement_date DESC
    """
    
    return frappe.db.sql(query, params, as_dict=1)