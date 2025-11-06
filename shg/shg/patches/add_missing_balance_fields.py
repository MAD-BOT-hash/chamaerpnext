import frappe

def execute():
    """Ensure missing financial fields exist in SHG Loan."""
    loan_fields = [
        {"fieldname": "total_payable", "fieldtype": "Currency", "label": "Total Payable"},
        {"fieldname": "total_repaid", "fieldtype": "Currency", "label": "Total Repaid"},
        {"fieldname": "outstanding_balance", "fieldtype": "Currency", "label": "Outstanding Balance"},
        {"fieldname": "loan_balance", "fieldtype": "Currency", "label": "Loan Balance"},
        {"fieldname": "balance_amount", "fieldtype": "Currency", "label": "Balance Amount"},
        {"fieldname": "overdue_amount", "fieldtype": "Currency", "label": "Overdue Amount"},
    ]

    for field in loan_fields:
        # Check if column exists in database
        if not frappe.db.has_column("SHG Loan", field["fieldname"]):
            # Add column to database using SQL
            frappe.db.sql(f"ALTER TABLE `tabSHG Loan` ADD COLUMN `{field['fieldname']}` DECIMAL(21,9) DEFAULT 0.000000000")
            frappe.msgprint(f"Added missing field {field['fieldname']} to SHG Loan")
        
        # Check if custom field exists in metadata
        if not frappe.db.exists("Custom Field", {"dt": "SHG Loan", "fieldname": field["fieldname"]}):
            # Create custom field for UI visibility
            custom_field = {
                "dt": "SHG Loan",
                "fieldname": field["fieldname"],
                "label": field["label"],
                "fieldtype": field["fieldtype"],
                "insert_after": "modified_by",  # Safe position
                "read_only": 1,
                "no_copy": 1
            }
            create_custom_field("SHG Loan", custom_field)
            frappe.msgprint(f"Added custom field {field['fieldname']} to SHG Loan UI")