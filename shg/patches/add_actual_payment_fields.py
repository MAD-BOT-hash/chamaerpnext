import frappe
from frappe.utils import cint

def execute():
    """Add actual_payment_date, actual_amount_paid, and payment_entry fields to SHG Loan Repayment Schedule doctype."""
    
    # Check if the fields already exist
    if not field_exists("SHG Loan Repayment Schedule", "actual_payment_date"):
        # Add actual_payment_date field
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "SHG Loan Repayment Schedule",
            "fieldname": "actual_payment_date",
            "label": "Actual Payment Date",
            "fieldtype": "Date",
            "insert_after": "status",
            "read_only": 0,
            "allow_on_submit": 1
        }).insert(ignore_permissions=True)
        print("Added actual_payment_date field to SHG Loan Repayment Schedule")

    if not field_exists("SHG Loan Repayment Schedule", "actual_amount_paid"):
        # Add actual_amount_paid field
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "SHG Loan Repayment Schedule",
            "fieldname": "actual_amount_paid",
            "label": "Actual Amount Paid",
            "fieldtype": "Currency",
            "insert_after": "actual_payment_date",
            "read_only": 0,
            "allow_on_submit": 1,
            "precision": 2
        }).insert(ignore_permissions=True)
        print("Added actual_amount_paid field to SHG Loan Repayment Schedule")

    if not field_exists("SHG Loan Repayment Schedule", "payment_entry"):
        # Add payment_entry field
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "SHG Loan Repayment Schedule",
            "fieldname": "payment_entry",
            "label": "Payment Entry",
            "fieldtype": "Link",
            "options": "Payment Entry",
            "insert_after": "actual_amount_paid",
            "read_only": 1
        }).insert(ignore_permissions=True)
        print("Added payment_entry field to SHG Loan Repayment Schedule")

    frappe.db.commit()

def field_exists(doctype, fieldname):
    """Check if a custom field already exists."""
    return frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname})