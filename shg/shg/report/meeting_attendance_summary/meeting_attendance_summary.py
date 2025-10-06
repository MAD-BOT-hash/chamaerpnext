import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("Meeting Date"),
            "fieldname": "meeting_date",
            "fieldtype": "Date",
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
            "label": _("Attendance Status"),
            "fieldname": "attendance_status",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Arrival Time"),
            "fieldname": "arrival_time",
            "fieldtype": "Time",
            "width": 120
        },
        {
            "label": _("Fine Amount"),
            "fieldname": "fine_amount",
            "fieldtype": "Currency",
            "width": 120
        }
    ]

def get_data(filters):
    conditions = ""
    if filters.get("from_date"):
        conditions += " AND ma.meeting_date >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND ma.meeting_date <= %(to_date)s"
    if filters.get("meeting"):
        conditions += " AND ma.meeting = %(meeting)s"
        
    query = f"""
        SELECT 
            ma.meeting_date,
            mad.meeting,
            mad.member,
            mad.member_name,
            mad.attendance_status,
            mad.arrival_time,
            mad.fine_amount
        FROM `tabSHG Member Attendance Detail` mad
        JOIN `tabSHG Member Attendance` ma ON mad.parent = ma.name
        WHERE ma.docstatus = 1 {conditions}
        ORDER BY ma.meeting_date DESC, mad.member_name
    """
    
    return frappe.db.sql(query, filters, as_dict=1)