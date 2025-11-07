import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
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
            "label": _("Current"),
            "fieldname": "current",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("1-30 Days"),
            "fieldname": "days_1_30",
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
        },
        {
            "label": _("Total Outstanding"),
            "fieldname": "total_outstanding",
            "fieldtype": "Currency",
            "width": 120
        }
    ]


def get_data(filters):
    conditions = ""
    params = {}
    
    if filters.get("member"):
        conditions += " AND l.member = %(member)s"
        params["member"] = filters.get("member")
    
    # Get all active loans with outstanding balances
    query = f"""
        SELECT 
            l.member,
            l.member_name,
            l.total_outstanding,
            l.next_due_date
        FROM `tabSHG Loan` l
        WHERE l.docstatus = 1 
            AND l.status IN ('Disbursed', 'Active', 'Overdue')
            AND COALESCE(l.total_outstanding, 0) > 0
            {conditions}
        ORDER BY l.member, l.next_due_date
    """
    
    loans = frappe.db.sql(query, params, as_dict=1)
    
    # Group by member and calculate aging buckets
    member_data = {}
    today = getdate()
    
    for loan in loans:
        member = loan.member
        if member not in member_data:
            member_data[member] = {
                "member": member,
                "member_name": loan.member_name,
                "current": 0,
                "days_1_30": 0,
                "days_31_60": 0,
                "days_61_90": 0,
                "days_90_plus": 0,
                "total_outstanding": 0
            }
        
        outstanding = flt(loan.total_outstanding)
        member_data[member]["total_outstanding"] += outstanding
        
        # Calculate days overdue
        if loan.next_due_date:
            days_overdue = (today - getdate(loan.next_due_date)).days
        else:
            days_overdue = 0
        
        # Categorize into aging buckets
        if days_overdue <= 0:
            member_data[member]["current"] += outstanding
        elif days_overdue <= 30:
            member_data[member]["days_1_30"] += outstanding
        elif days_overdue <= 60:
            member_data[member]["days_31_60"] += outstanding
        elif days_overdue <= 90:
            member_data[member]["days_61_90"] += outstanding
        else:
            member_data[member]["days_90_plus"] += outstanding
    
    # Convert to list
    data = list(member_data.values())
    
    return data