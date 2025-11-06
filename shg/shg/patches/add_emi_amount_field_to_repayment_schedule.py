import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def execute():
    """Add missing emi_amount field to SHG Loan Repayment Schedule."""
    
    # Check if field already exists
    if not frappe.db.exists("Custom Field", {"dt": "SHG Loan Repayment Schedule", "fieldname": "emi_amount"}):
        field = {
            "fieldname": "emi_amount",
            "label": "EMI Amount",
            "fieldtype": "Currency",
            "options": "KES",
            "insert_after": "due_date",
            "read_only": 1,
            "in_list_view": 1,
            "columns": 2
        }
        create_custom_field("SHG Loan Repayment Schedule", field)
        frappe.msgprint("Added EMI Amount field to SHG Loan Repayment Schedule")
    
    # Update existing schedule rows to populate emi_amount from total_payment if needed
    schedules = frappe.get_all("SHG Loan Repayment Schedule", 
                             filters={"emi_amount": ["=", 0]},
                             fields=["name", "total_payment"])
    
    for schedule in schedules:
        frappe.db.set_value("SHG Loan Repayment Schedule", schedule.name, 
                           "emi_amount", schedule.total_payment)
    
    frappe.db.commit()