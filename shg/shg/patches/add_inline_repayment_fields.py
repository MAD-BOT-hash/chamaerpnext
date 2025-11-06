import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def execute():
    """Add inline repayment fields to SHG Loan Repayment Schedule and SHG Loan."""
    
    # Fields for SHG Loan Repayment Schedule child table
    schedule_fields = [
        {
            "fieldname": "pay_now",
            "label": "Pay Now",
            "fieldtype": "Check",
            "insert_after": "status",
            "allow_on_submit": 1
        },
        {
            "fieldname": "amount_to_pay",
            "label": "Amount to Pay",
            "fieldtype": "Currency",
            "insert_after": "pay_now",
            "allow_on_submit": 1
        },
        {
            "fieldname": "remaining_amount",
            "label": "Remaining Amount",
            "fieldtype": "Currency",
            "insert_after": "amount_to_pay",
            "read_only": 1,
            "allow_on_submit": 1
        }
    ]
    
    # Add fields to SHG Loan Repayment Schedule
    for field in schedule_fields:
        if not frappe.db.exists("Custom Field", {"dt": "SHG Loan Repayment Schedule", "fieldname": field["fieldname"]}):
            field["dt"] = "SHG Loan Repayment Schedule"
            create_custom_field(field)
            frappe.msgprint(f"Added field {field['fieldname']} to SHG Loan Repayment Schedule")
    
    # Fields for SHG Loan parent document
    loan_fields = [
        {
            "fieldname": "inline_repayment_section",
            "label": "Inline Repayment",
            "fieldtype": "Section Break",
            "insert_after": "repayment_schedule",
        },
        {
            "fieldname": "emi_breakdown",
            "label": "EMI Breakdown",
            "fieldtype": "HTML",
            "insert_after": "inline_repayment_section",
        },
        {
            "fieldname": "inline_total_selected",
            "label": "Total Selected",
            "fieldtype": "Currency",
            "insert_after": "emi_breakdown",
            "read_only": 1,
        },
        {
            "fieldname": "inline_overdue",
            "label": "Overdue Amount",
            "fieldtype": "Currency",
            "insert_after": "inline_total_selected",
            "read_only": 1,
        },
        {
            "fieldname": "inline_outstanding",
            "label": "Outstanding Amount",
            "fieldtype": "Currency",
            "insert_after": "inline_overdue",
            "read_only": 1,
        }
    ]
    
    # Add fields to SHG Loan
    for field in loan_fields:
        if not frappe.db.exists("Custom Field", {"dt": "SHG Loan", "fieldname": field["fieldname"]}):
            field["dt"] = "SHG Loan"
            create_custom_field(field)
            frappe.msgprint(f"Added field {field['fieldname']} to SHG Loan")