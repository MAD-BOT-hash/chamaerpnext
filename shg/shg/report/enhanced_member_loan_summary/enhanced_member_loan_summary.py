import frappe
from frappe import _
from frappe.utils import getdate, today, flt

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
            "label": _("Loan Principal"),
            "fieldname": "loan_principal",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Interest Accrued"),
            "fieldname": "interest_accrued",
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
            "label": _("Amount Paid to Date"),
            "fieldname": "amount_paid",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Current Balance"),
            "fieldname": "current_balance",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Interest Type"),
            "fieldname": "interest_type",
            "fieldtype": "Data",
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
        conditions += " AND l.loan_status = %(status)s"
        params["status"] = filters.get("status")
        
    query = f"""
        SELECT 
            l.member_name,
            l.name as loan_id,
            l.disbursement_date,
            l.loan_amount as loan_principal,
            l.total_interest_payable as interest_accrued,
            l.total_payable_amount as total_payable,
            l.total_amount_paid as amount_paid,
            l.outstanding_amount as current_balance,
            l.interest_type,
            l.interest_rate,
            l.loan_period_months,
            l.loan_status as status,
            l.next_due_date
        FROM `tabSHG Loan` l
        WHERE l.docstatus = 1 {conditions}
        ORDER BY l.disbursement_date DESC
    """
    
    return frappe.db.sql(query, params, as_dict=1)