# Copyright (c) 2025 SHG Solutions
# License: MIT

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("Installment No"),
            "fieldname": "installment_no",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": _("Due Date"),
            "fieldname": "due_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Principal"),
            "fieldname": "principal_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Interest"),
            "fieldname": "interest_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Total Payment"),
            "fieldname": "total_payment",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Amount Paid"),
            "fieldname": "amount_paid",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Unpaid Balance"),
            "fieldname": "unpaid_balance",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Actual Payment Date"),
            "fieldname": "actual_payment_date",
            "fieldtype": "Date",
            "width": 120
        }
    ]

def get_data(filters):
    conditions = ""
    if filters.get("loan"):
        conditions += " AND parent = %(loan)s"
    if filters.get("member"):
        conditions += " AND parent IN (SELECT name FROM `tabSHG Loan` WHERE member = %(member)s)"
    if filters.get("from_date"):
        conditions += " AND due_date >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND due_date <= %(to_date)s"
        
    data = frappe.db.sql("""
        SELECT 
            installment_no,
            due_date,
            principal_component AS principal_amount,
            interest_component AS interest_amount,
            total_payment,
            amount_paid,
            unpaid_balance,
            status,
            actual_payment_date
        FROM `tabSHG Loan Repayment Schedule`
        WHERE docstatus = 1 {conditions}
        ORDER BY due_date
    """.format(conditions=conditions), filters, as_dict=1)
    
    return data