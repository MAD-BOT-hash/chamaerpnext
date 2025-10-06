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
            "label": _("Payment Date"),
            "fieldname": "payment_date",
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
        },
        {
            "label": _("Actual Payment Date"),
            "fieldname": "actual_payment_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Actual Amount Paid"),
            "fieldname": "actual_amount_paid",
            "fieldtype": "Currency",
            "width": 120
        }
    ]

def get_data(filters):
    if not filters or not filters.get("loan"):
        return []
    
    # Get loan details
    loan = frappe.get_doc("SHG Loan", filters.loan)
    
    # Get repayment schedule
    schedule = frappe.db.sql("""
        SELECT 
            name,
            idx as installment_no,
            payment_date,
            principal_amount,
            interest_amount,
            total_payment,
            balance_amount,
            status,
            actual_payment_date,
            actual_amount_paid
        FROM `tabSHG Loan Repayment Schedule`
        WHERE parent = %s
        ORDER BY payment_date
    """, filters.loan, as_dict=1)
    
    return schedule