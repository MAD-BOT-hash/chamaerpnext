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
            "label": _("Posting Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Loan"),
            "fieldname": "loan",
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
            "label": _("Transaction Type"),
            "fieldname": "transaction_type",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Principal"),
            "fieldname": "principal",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Interest"),
            "fieldname": "interest",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Penalty"),
            "fieldname": "penalty",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Total Amount"),
            "fieldname": "total_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Remarks"),
            "fieldname": "remarks",
            "fieldtype": "Data",
            "width": 200
        }
    ]


def get_data(filters):
    conditions = ""
    params = {}
    
    if filters.get("loan"):
        conditions += " AND t.loan = %(loan)s"
        params["loan"] = filters.get("loan")
        
    if filters.get("member"):
        conditions += " AND t.member = %(member)s"
        params["member"] = filters.get("member")
        
    if filters.get("transaction_type"):
        conditions += " AND t.transaction_type = %(transaction_type)s"
        params["transaction_type"] = filters.get("transaction_type")
        
    if filters.get("from_date"):
        conditions += " AND t.posting_date >= %(from_date)s"
        params["from_date"] = filters.get("from_date")
        
    if filters.get("to_date"):
        conditions += " AND t.posting_date <= %(to_date)s"
        params["to_date"] = filters.get("to_date")
    
    query = f"""
        SELECT 
            t.posting_date,
            t.loan,
            t.member,
            t.transaction_type,
            COALESCE(t.principal, 0) as principal,
            COALESCE(t.interest, 0) as interest,
            COALESCE(t.penalty, 0) as penalty,
            COALESCE(t.amount, 0) as total_amount,
            t.remarks
        FROM `tabSHG Loan Transaction` t
        WHERE t.docstatus = 1 {conditions}
        ORDER BY t.posting_date DESC, t.creation DESC
    """
    
    data = frappe.db.sql(query, params, as_dict=1)
    
    return data