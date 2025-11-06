import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def execute():
    """Add missing EMI-related fields to SHG Loan Repayment Schedule DocType."""
    fields_to_add = [
        {
            "fieldname": "emi_amount",
            "label": "EMI Amount",
            "fieldtype": "Currency",
            "insert_after": "due_date",
            "read_only": 1,
        },
        {
            "fieldname": "principal_component",
            "label": "Principal Component",
            "fieldtype": "Currency",
            "insert_after": "emi_amount",
            "read_only": 1,
        },
        {
            "fieldname": "interest_component",
            "label": "Interest Component",
            "fieldtype": "Currency",
            "insert_after": "principal_component",
            "read_only": 1,
        },
    ]

    for df in fields_to_add:
        # Check if the field exists in both DB schema and UI form
        if not frappe.db.has_column("SHG Loan Repayment Schedule", df["fieldname"]):
            if not frappe.db.exists("Custom Field", {"dt": "SHG Loan Repayment Schedule", "fieldname": df["fieldname"]}):
                create_custom_field("SHG Loan Repayment Schedule", df)
                frappe.log(f"✅ Added field {df['fieldname']} to SHG Loan Repayment Schedule")
            else:
                frappe.log(f"⚠️ UI-level field {df['fieldname']} exists but column missing — skipping DB create")
        else:
            frappe.log(f"ℹ️ Field {df['fieldname']} already exists — skipping")