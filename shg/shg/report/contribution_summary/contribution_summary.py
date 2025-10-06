import frappe
from frappe import _
from frappe.utils import getdate

def execute(filters=None):
    if not filters:
        filters = {}
        
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("Date"),
            "fieldname": "date",
            "fieldtype": "Date",
            "width": 120
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
            "label": _("Contribution Type"),
            "fieldname": "contribution_type",
            "fieldtype": "Link",
            "options": "SHG Contribution Type",
            "width": 150
        },
        {
            "label": _("Amount"),
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Payment Method"),
            "fieldname": "payment_method",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Reference Number"),
            "fieldname": "reference_number",
            "fieldtype": "Data",
            "width": 150
        }
    ]

def get_data(filters):
    conditions = ""
    params = {}
    
    if filters.get("from_date"):
        conditions += " AND c.contribution_date >= %(from_date)s"
        params["from_date"] = filters.get("from_date")
    if filters.get("to_date"):
        conditions += " AND c.contribution_date <= %(to_date)s"
        params["to_date"] = filters.get("to_date")
    if filters.get("contribution_type"):
        conditions += " AND c.contribution_type_link = %(contribution_type)s"
        params["contribution_type"] = filters.get("contribution_type")
        
    if conditions:
        conditions = conditions.lstrip(" AND")
        query = f"""
            SELECT 
                c.contribution_date as date,
                c.member,
                c.member_name,
                c.contribution_type_link as contribution_type,
                c.amount,
                c.payment_method,
                c.reference_number
            FROM `tabSHG Contribution` c
            WHERE c.docstatus = 1 AND {conditions}
            ORDER BY c.contribution_date DESC
        """
    else:
        query = """
            SELECT 
                c.contribution_date as date,
                c.member,
                c.member_name,
                c.contribution_type_link as contribution_type,
                c.amount,
                c.payment_method,
                c.reference_number
            FROM `tabSHG Contribution` c
            WHERE c.docstatus = 1
            ORDER BY c.contribution_date DESC
        """
    
    return frappe.db.sql(query, params, as_dict=1)