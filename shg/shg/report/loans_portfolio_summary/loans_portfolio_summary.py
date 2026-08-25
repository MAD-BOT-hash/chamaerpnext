import frappe
from frappe import _
from frappe.utils import flt, getdate


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
            "label": _("Outstanding Principal"),
            "fieldname": "outstanding_principal",
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
            "label": _("Interest Paid"),
            "fieldname": "interest_paid",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Total Outstanding"),
            "fieldname": "total_outstanding",
            "fieldtype": "Currency",
            "width": 120
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
            "fieldtype": "Currency",
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
        }
    ]


def get_data(filters):
    conditions = ""
    params = {}
    
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
            l.balance_amount as outstanding_principal,
            l.total_interest_payable,
            (l.total_interest_payable - COALESCE(l.total_amount_paid - l.total_repaid, 0)) as interest_paid,
            (l.balance_amount + COALESCE(l.total_interest_payable, 0)) as total_outstanding,
            l.next_due_date,
            l.status,
            l.disbursement_date,
            COALESCE(l.overdue_amount, 0) as days_overdue
        FROM `tabSHG Loan` l
        WHERE l.docstatus = 1 {conditions}
        ORDER BY l.disbursement_date DESC
    """
    
    data = frappe.db.sql(query, params, as_dict=1)
    
    return data