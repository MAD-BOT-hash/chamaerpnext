# Copyright (c) 2025, SHG Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, fmt_money

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    """Return columns for the report"""
    columns = [
        {
            "label": _("Member ID"),
            "fieldname": "member_id",
            "fieldtype": "Link",
            "options": "SHG Member",
            "width": 120
        },
        {
            "label": _("Member Name"),
            "fieldname": "member_name",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("January"),
            "fieldname": "jan",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("February"),
            "fieldname": "feb",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("March"),
            "fieldname": "mar",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("April"),
            "fieldname": "apr",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("May"),
            "fieldname": "may",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("June"),
            "fieldname": "jun",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("July"),
            "fieldname": "jul",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("August"),
            "fieldname": "aug",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("September"),
            "fieldname": "sep",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("October"),
            "fieldname": "oct",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("November"),
            "fieldname": "nov",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("December"),
            "fieldname": "dec",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Total Present"),
            "fieldname": "total_present",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": _("Attendance %"),
            "fieldname": "attendance_percentage",
            "fieldtype": "Percent",
            "width": 120
        }
    ]
    
    return columns

def get_data(filters):
    """Return data for the report"""
    # Get all active members
    members = frappe.get_all("SHG Member", 
                            filters={"membership_status": "Active"},
                            fields=["name", "member_name"],
                            order_by="member_name")
    
    # Get year from filters or use current year
    year = filters.get("year") if filters and filters.get("year") else frappe.utils.nowdate()[:4]
    
    data = []
    
    for member in members:
        # Get attendance records for this member for the specified year
        attendance_records = frappe.db.sql("""
            SELECT 
                MONTH(sa.meeting_date) as month,
                sad.attendance_status
            FROM `tabSHG Member Attendance Detail` sad
            JOIN `tabSHG Member Attendance` sa ON sad.parent = sa.name
            WHERE sad.member = %s 
            AND YEAR(sa.meeting_date) = %s
            AND sa.docstatus = 1
            ORDER BY sa.meeting_date
        """, (member.name, year), as_dict=True)
        
        # Initialize monthly attendance data
        monthly_data = {
            1: [], 2: [], 3: [], 4: [], 5: [], 6: [],
            7: [], 8: [], 9: [], 10: [], 11: [], 12: []
        }
        
        # Populate monthly attendance data
        for record in attendance_records:
            monthly_data[record.month].append(record.attendance_status)
        
        # Calculate monthly attendance summary
        monthly_summary = {}
        total_present = 0
        total_meetings = 0
        
        for month in range(1, 13):
            present = monthly_data[month].count("Present") + monthly_data[month].count("Late") + monthly_data[month].count("Excused")
            total = len(monthly_data[month])
            
            if total > 0:
                percentage = (present / total) * 100
                monthly_summary[month] = f"{present}/{total} ({percentage:.0f}%)"
                total_present += present
                total_meetings += total
            else:
                monthly_summary[month] = "0/0 (0%)"
        
        # Calculate overall attendance percentage
        overall_percentage = (total_present / total_meetings * 100) if total_meetings > 0 else 0
        
        # Prepare row data
        row = {
            "member_id": member.name,
            "member_name": member.member_name,
            "jan": monthly_summary[1],
            "feb": monthly_summary[2],
            "mar": monthly_summary[3],
            "apr": monthly_summary[4],
            "may": monthly_summary[5],
            "jun": monthly_summary[6],
            "jul": monthly_summary[7],
            "aug": monthly_summary[8],
            "sep": monthly_summary[9],
            "oct": monthly_summary[10],
            "nov": monthly_summary[11],
            "dec": monthly_summary[12],
            "total_present": total_present,
            "attendance_percentage": overall_percentage
        }
        
        data.append(row)
    
    return data