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
            "fieldname": "fine_date",
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
            "label": _("Fine Reason"),
            "fieldname": "fine_reason",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Fine Amount"),
            "fieldname": "fine_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Meeting"),
            "fieldname": "meeting",
            "fieldtype": "Link",
            "options": "SHG Meeting",
            "width": 150
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        }
    ]

def get_data(filters):
    conditions = ""
    if filters.get("from_date"):
        conditions += " AND mf.fine_date >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND mf.fine_date <= %(to_date)s"
    if filters.get("member"):
        conditions += " AND mf.member = %(member)s"
        
    query = f"""
        SELECT 
            mf.fine_date,
            mf.member,
            mf.member_name,
            mf.fine_reason,
            mf.fine_amount,
            mf.meeting,
            mf.status
        FROM `tabSHG Meeting Fine` mf
        WHERE mf.docstatus = 1 {conditions}
        ORDER BY mf.fine_date DESC
    """
    
    return frappe.db.sql(query, filters, as_dict=1)