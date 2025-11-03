# Copyright (c) 2025 SHG Solutions
# License: MIT

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
            "label": _("Outstanding Amount"),
            "fieldname": "outstanding_amount",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Active Loans"),
            "fieldname": "active_loans",
            "fieldtype": "Int",
            "width": 120
        }
    ]

def get_data(filters):
    conditions = ""
    if filters.get("from_date"):
        conditions += " AND l.disbursement_date >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND l.disbursement_date <= %(to_date)s"
        
    # Get monthly summary
    data = frappe.db.sql("""
        SELECT 
            DATE_FORMAT(l.disbursement_date, '%%Y-%%m') AS month,
            SUM(l.loan_amount) AS disbursed_amount,
            SUM(l.total_repaid) AS repaid_amount,
            SUM(l.balance_amount) AS outstanding_amount,
            COUNT(l.name) AS active_loans
        FROM `tabSHG Loan` l
        WHERE l.docstatus = 1 AND l.status = 'Disbursed' {conditions}
        GROUP BY DATE_FORMAT(l.disbursement_date, '%%Y-%%m')
        ORDER BY month
    """.format(conditions=conditions), filters, as_dict=1)
    
    return data