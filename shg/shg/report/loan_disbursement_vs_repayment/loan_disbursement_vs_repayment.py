import frappe
from frappe import _
from frappe.utils import getdate

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("Month"),
            "fieldname": "month",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Disbursed Amount"),
            "fieldname": "disbursed_amount",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Repaid Amount"),
            "fieldname": "repaid_amount",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Net Change"),
            "fieldname": "net_change",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Cumulative Balance"),
            "fieldname": "cumulative_balance",
            "fieldtype": "Currency",
            "width": 150
        }
    ]

def get_data(filters):
    conditions_loan = ""
    conditions_repayment = ""
    params = {}
    
    if filters.get("from_date"):
        conditions_loan += " AND l.disbursement_date >= %(from_date)s"
        conditions_repayment += " AND r.posting_date >= %(from_date)s"
        params["from_date"] = filters.get("from_date")
        
    if filters.get("to_date"):
        conditions_loan += " AND l.disbursement_date <= %(to_date)s"
        conditions_repayment += " AND r.posting_date <= %(to_date)s"
        params["to_date"] = filters.get("to_date")
        
    if filters.get("member"):
        conditions_loan += " AND l.member = %(member)s"
        conditions_repayment += " AND r.member = %(member)s"
        params["member"] = filters.get("member")
        
    # Get all months with either disbursements or repayments
    months_query = """
        SELECT DISTINCT DATE_FORMAT(date, '%%Y-%%m') AS month
        FROM (
            SELECT disbursement_date AS date
            FROM `tabSHG Loan`
            WHERE docstatus = 1 AND status = 'Disbursed' {conditions_loan}
            
            UNION
            
            SELECT posting_date AS date
            FROM `tabSHG Loan Repayment`
            WHERE docstatus = 1 {conditions_repayment}
        ) dates
        ORDER BY month
    """.format(conditions_loan=conditions_loan, conditions_repayment=conditions_repayment)
    
    months = frappe.db.sql(months_query, params, as_dict=1)
    
    # Get disbursement data by month
    disbursement_query = """
        SELECT 
            DATE_FORMAT(disbursement_date, '%%Y-%%m') AS month,
            SUM(loan_amount) AS disbursed_amount
        FROM `tabSHG Loan`
        WHERE docstatus = 1 AND status = 'Disbursed' {conditions_loan}
        GROUP BY DATE_FORMAT(disbursement_date, '%%Y-%%m')
    """.format(conditions_loan=conditions_loan)
    
    disbursements = frappe.db.sql(disbursement_query, params, as_dict=1)
    disbursement_dict = {d.month: d.disbursed_amount for d in disbursements}
    
    # Get repayment data by month
    repayment_query = """
        SELECT 
            DATE_FORMAT(posting_date, '%%Y-%%m') AS month,
            SUM(total_paid) AS repaid_amount
        FROM `tabSHG Loan Repayment`
        WHERE docstatus = 1 {conditions_repayment}
        GROUP BY DATE_FORMAT(posting_date, '%%Y-%%m')
    """.format(conditions_repayment=conditions_repayment)
    
    repayments = frappe.db.sql(repayment_query, params, as_dict=1)
    repayment_dict = {r.month: r.repaid_amount for r in repayments}
    
    # Combine data
    result = []
    cumulative_balance = 0
    
    for month_row in months:
        month = month_row.month
        disbursed_amount = disbursement_dict.get(month, 0)
        repaid_amount = repayment_dict.get(month, 0)
        net_change = disbursed_amount - repaid_amount
        cumulative_balance += net_change
        
        result.append({
            "month": month,
            "disbursed_amount": disbursed_amount,
            "repaid_amount": repaid_amount,
            "net_change": net_change,
            "cumulative_balance": cumulative_balance
        })
    
    return result