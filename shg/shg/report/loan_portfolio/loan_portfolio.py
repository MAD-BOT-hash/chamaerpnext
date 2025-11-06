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
            "label": _("Total Interest Payable"),
            "fieldname": "total_interest_payable",
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
            "label": _("Paid %"),
            "fieldname": "paid_percentage",
            "fieldtype": "Percent",
            "width": 100
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
    params = {"today": getdate(today())}
    
    if filters.get("status"):
        conditions += " AND l.status = %(status)s"
        params["status"] = filters.get("status")
        
    if filters.get("member"):
        conditions += " AND l.member = %(member)s"
        params["member"] = filters.get("member")
        
    if filters.get("from_date"):
        conditions += " AND l.disbursement_date >= %(from_date)s"
        params["from_date"] = filters.get("from_date")
        
    if filters.get("to_date"):
        conditions += " AND l.disbursement_date <= %(to_date)s"
        params["to_date"] = filters.get("to_date")
        
    query = f"""
        SELECT 
            l.name as loan_id,
            l.member,
            l.member_name,
            l.loan_amount,
            l.total_interest_payable,
            l.total_payable,
            l.total_repaid as paid_to_date,
            l.balance_amount as outstanding,
            CASE 
                WHEN l.next_due_date < %(today)s AND l.balance_amount > 0 THEN l.overdue_amount
                ELSE 0
            END as overdue,
            CASE 
                WHEN l.total_payable > 0 THEN (l.total_repaid / l.total_payable) * 100
                ELSE 0
            END as paid_percentage,
            l.interest_rate,
            l.loan_period_months,
            l.status,
            l.disbursement_date,
            l.next_due_date
        FROM `tabSHG Loan` l
        WHERE l.docstatus = 1 {conditions}
        ORDER BY l.disbursement_date DESC
    """
    
    return frappe.db.sql(query, params, as_dict=1)