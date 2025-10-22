# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("Payment Date"),
            "fieldname": "payment_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Payment Entry"),
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "SHG Multi Member Payment",
            "width": 150
        },
        {
            "label": _("Payment Method"),
            "fieldname": "payment_method",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Company"),
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 120
        },
        {
            "label": _("Account"),
            "fieldname": "account",
            "fieldtype": "Link",
            "options": "Account",
            "width": 150
        },
        {
            "label": _("Total Invoices"),
            "fieldname": "total_invoices",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": _("Total Amount"),
            "fieldname": "total_amount",
            "fieldtype": "Currency",
            "width": 120
        }
    ]

def get_data(filters):
    conditions = ""
    if filters.get("from_date"):
        conditions += " AND payment_date >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND payment_date <= %(to_date)s"
    if filters.get("company"):
        conditions += " AND company = %(company)s"
    if filters.get("payment_method"):
        conditions += " AND payment_method = %(payment_method)s"
        
    data = frappe.db.sql("""
        SELECT 
            name,
            payment_date,
            payment_method,
            company,
            account,
            total_selected_invoices as total_invoices,
            total_amount
        FROM 
            `tabSHG Multi Member Payment`
        WHERE 
            docstatus = 1
            {conditions}
        ORDER BY 
            payment_date DESC
    """.format(conditions=conditions), filters, as_dict=1)
    
    return data