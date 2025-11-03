# Copyright (c) 2025 SHG Solutions
# License: MIT

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
            "label": _("Loan"),
            "fieldname": "loan",
            "fieldtype": "Link",
            "options": "SHG Loan",
            "width": 150
        },
        {
            "label": _("Total Outstanding"),
            "fieldname": "total_outstanding",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Current"),
            "fieldname": "current",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("0-30 Days"),
            "fieldname": "days_0_30",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("31-60 Days"),
            "fieldname": "days_31_60",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("61-90 Days"),
            "fieldname": "days_61_90",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("90+ Days"),
            "fieldname": "days_90_plus",
            "fieldtype": "Currency",
            "width": 120
        }
    ]

def get_data(filters):
    conditions = ""
    if filters.get("member"):
        conditions += " AND l.member = %(member)s"
    if filters.get("loan"):
        conditions += " AND l.name = %(loan)s"
        
    # Get today's date
    today_date = getdate(today())
    
    data = frappe.db.sql("""
        SELECT 
            l.member,
            l.member_name,
            l.name AS loan,
            l.balance_amount AS total_outstanding,
            SUM(CASE WHEN s.due_date >= %(today)s THEN s.unpaid_balance ELSE 0 END) AS current,
            SUM(CASE WHEN s.due_date < %(today)s AND s.due_date >= DATE_SUB(%(today)s, INTERVAL 30 DAY) THEN s.unpaid_balance ELSE 0 END) AS days_0_30,
            SUM(CASE WHEN s.due_date < DATE_SUB(%(today)s, INTERVAL 30 DAY) AND s.due_date >= DATE_SUB(%(today)s, INTERVAL 60 DAY) THEN s.unpaid_balance ELSE 0 END) AS days_31_60,
            SUM(CASE WHEN s.due_date < DATE_SUB(%(today)s, INTERVAL 60 DAY) AND s.due_date >= DATE_SUB(%(today)s, INTERVAL 90 DAY) THEN s.unpaid_balance ELSE 0 END) AS days_61_90,
            SUM(CASE WHEN s.due_date < DATE_SUB(%(today)s, INTERVAL 90 DAY) THEN s.unpaid_balance ELSE 0 END) AS days_90_plus
        FROM `tabSHG Loan` l
        LEFT JOIN `tabSHG Loan Repayment Schedule` s ON s.parent = l.name AND s.docstatus = 1 AND s.unpaid_balance > 0
        WHERE l.docstatus = 1 AND l.balance_amount > 0 {conditions}
        GROUP BY l.name, l.member, l.member_name, l.balance_amount
        ORDER BY l.member_name
    """.format(conditions=conditions), {"today": today_date, **filters}, as_dict=1)
    
    return data