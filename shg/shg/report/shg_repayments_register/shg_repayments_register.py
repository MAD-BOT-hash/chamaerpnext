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
            "label": _("Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Repayment ID"),
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "SHG Loan Repayment",
            "width": 150
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
            "fieldname": "member_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Amount"),
            "fieldname": "total_paid",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Payment Method"),
            "fieldname": "payment_method",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Reference No"),
            "fieldname": "reference_number",
            "fieldtype": "Data",
            "width": 150
        }
    ]

def get_data(filters):
    conditions = ""
    if filters.get("from_date"):
        conditions += " AND r.posting_date >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND r.posting_date <= %(to_date)s"
    if filters.get("member"):
        conditions += " AND r.member = %(member)s"
    if filters.get("loan"):
        conditions += " AND r.loan = %(loan)s"
    if filters.get("payment_method"):
        conditions += " AND r.payment_method = %(payment_method)s"
        
    data = frappe.db.sql("""
        SELECT 
            r.posting_date,
            r.name,
            r.loan,
            r.member_name,
            r.total_paid,
            r.payment_method,
            r.reference_number
        FROM `tabSHG Loan Repayment` r
        WHERE r.docstatus = 1 {conditions}
        ORDER BY r.posting_date DESC
    """.format(conditions=conditions), filters, as_dict=1)
    
    return data