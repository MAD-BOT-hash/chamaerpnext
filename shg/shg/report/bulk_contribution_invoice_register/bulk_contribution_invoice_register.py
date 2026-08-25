import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": _("Bulk Invoice ID"),
            "fieldname": "bulk_invoice_id",
            "fieldtype": "Link",
            "options": "SHG Bulk Contribution Invoice",
            "width": 150
        },
        {
            "label": _("Invoice Date"),
            "fieldname": "invoice_date",
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
            "label": _("Generated Invoice"),
            "fieldname": "generated_invoice",
            "fieldtype": "Link",
            "options": "SHG Contribution Invoice",
            "width": 150
        },
        {
            "label": _("Amount"),
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Error Message"),
            "fieldname": "error_message",
            "fieldtype": "Data",
            "width": 300
        },
        {
            "label": _("Created On"),
            "fieldname": "creation",
            "fieldtype": "Datetime",
            "width": 150
        }
    ]


def get_data(filters):
    conditions = ""
    params = {}
    
    if filters.get("from_date"):
        conditions += " AND bci.invoice_date >= %(from_date)s"
        params["from_date"] = filters.get("from_date")
    
    if filters.get("to_date"):
        conditions += " AND bci.invoice_date <= %(to_date)s"
        params["to_date"] = filters.get("to_date")
    
    if filters.get("bulk_invoice"):
        conditions += " AND bci.name = %(bulk_invoice)s"
        params["bulk_invoice"] = filters.get("bulk_invoice")
    
    if filters.get("member"):
        conditions += " AND bcii.member = %(member)s"
        params["member"] = filters.get("member")
    
    if filters.get("status"):
        conditions += " AND bcii.status = %(status)s"
        params["status"] = filters.get("status")
    
    query = f"""
        SELECT 
            bci.name as bulk_invoice_id,
            bci.invoice_date,
            bcii.member,
            bcii.member_name,
            bcii.generated_invoice,
            bcii.amount,
            bcii.status,
            bcii.error_message,
            bci.creation
        FROM `tabSHG Bulk Contribution Invoice` bci
        JOIN `tabSHG Bulk Contribution Invoice Item` bcii ON bcii.parent = bci.name
        WHERE bci.docstatus = 0 {conditions}
        ORDER BY bci.creation DESC, bcii.member
    """
    
    data = frappe.db.sql(query, params, as_dict=1)
    
    return data
