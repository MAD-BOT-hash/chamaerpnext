import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def execute():
    """Add missing fields for Recalculate Loan Summary feature to SHG Loan DocType."""
    
    # Fields to add to SHG Loan DocType
    loan_fields = [
        {
            "fieldname": "total_principal_payable",
            "label": "Total Principal Payable",
            "fieldtype": "Currency",
            "insert_after": "total_payable",
            "read_only": 1,
            "allow_on_submit": 1,
            "precision": 2
        },
        {
            "fieldname": "total_amount_paid",
            "label": "Total Amount Paid",
            "fieldtype": "Currency",
            "insert_after": "total_repaid",
            "read_only": 1,
            "allow_on_submit": 1,
            "precision": 2
        },
        {
            "fieldname": "outstanding_amount",
            "label": "Outstanding Amount",
            "fieldtype": "Currency",
            "insert_after": "balance_amount",
            "read_only": 1,
            "allow_on_submit": 1,
            "precision": 2
        },
        {
            "fieldname": "loan_status",
            "label": "Loan Status",
            "fieldtype": "Select",
            "options": "\nActive\nCompleted\nOverdue\nDefaulted",
            "insert_after": "status",
            "read_only": 1,
            "allow_on_submit": 1
        }
    ]
    
    # Add fields to SHG Loan DocType
    for field in loan_fields:
        # Check if field already exists to ensure idempotency
        if not frappe.db.exists("Custom Field", {"dt": "SHG Loan", "fieldname": field["fieldname"]}):
            create_custom_field("SHG Loan", field)
            frappe.msgprint(f"Added field {field['fieldname']} to SHG Loan")