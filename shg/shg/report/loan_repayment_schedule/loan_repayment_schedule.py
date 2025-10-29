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
            "width": 100
        },
        {
            "label": _("Due Date"),
            "fieldname": "due_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Principal Amount"),
            "fieldname": "principal_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Interest Amount"),
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
            "label": _("Balance Amount"),
            "fieldname": "balance_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        }
    ]

def get_data(filters):
    if not filters or not filters.get("loan"):
        return []
    
    # Get repayment schedule from the child table
    schedule = frappe.db.sql("""
        SELECT 
            installment_no,
            due_date,
            principal_amount,
            interest_amount,
            total_payment,
            balance_amount,
            status
        FROM `tabSHG Loan Repayment Schedule`
        WHERE parent = %s
        ORDER BY due_date
    """, filters.loan, as_dict=1)
    
    return schedule