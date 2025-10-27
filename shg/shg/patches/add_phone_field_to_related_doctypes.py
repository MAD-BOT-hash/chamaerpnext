import frappe

def execute():
    """Ensure phone_number column exists in SHG Member, Contribution, and Loan doctypes."""
    doctypes = ["SHG Member", "SHG Contribution", "SHG Loan"]

    for dt in doctypes:
        table_name = f"`tab{dt}`"

        # Check if the column already exists
        col_exists = frappe.db.sql(
            f"SHOW COLUMNS FROM {table_name} LIKE 'phone_number'"
        )

        if not col_exists:
            frappe.db.sql(f"ALTER TABLE {table_name} ADD COLUMN phone_number VARCHAR(140)")
            frappe.logger().info(f"✅ Added 'phone_number' column to {dt}")
        else:
            frappe.logger().info(f"ℹ️ Column 'phone_number' already exists in {dt}")

    frappe.db.commit()
    frappe.msgprint("✅ Phone number field ensured in SHG Member, SHG Contribution, and SHG Loan.")