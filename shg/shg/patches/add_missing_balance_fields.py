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
            frappe.msgprint(f"Added missing field {field['fieldname']} to SHG Loan database")
        
        # Check if custom field exists in metadata
        if not frappe.db.exists("Custom Field", {"dt": "SHG Loan", "fieldname": field["fieldname"]}):
            # Create custom field document for UI visibility
            custom_field = frappe.new_doc("Custom Field")
            custom_field.dt = "SHG Loan"
            custom_field.fieldname = field["fieldname"]
            custom_field.label = field["label"]
            custom_field.fieldtype = field["fieldtype"]
            custom_field.insert_after = "modified_by"  # Safe position
            custom_field.read_only = 1
            custom_field.no_copy = 1
            custom_field.insert(ignore_permissions=True)
            frappe.msgprint(f"Added custom field {field['fieldname']} to SHG Loan UI")