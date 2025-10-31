import frappe

def execute():
    """
    Add missing loan_eligibility_flag and has_overdue_loans columns to SHG Member table
    """

    table_name = "tabSHG Member"

    # Define columns to add if they don't exist
    columns = {
        "loan_eligibility_flag": "INT(1) DEFAULT 1",
        "has_overdue_loans": "INT(1) DEFAULT 0"
    }

    existing_columns = frappe.db.get_table_columns("SHG Member")

    for column, definition in columns.items():
        if column not in existing_columns:
            frappe.db.sql(f"ALTER TABLE `{table_name}` ADD COLUMN IF NOT EXISTS `{column}` {definition}")
            frappe.logger().info(f"Added column {column} to {table_name}")
        else:
            frappe.logger().info(f"Column {column} already exists in {table_name}")

    frappe.db.commit()