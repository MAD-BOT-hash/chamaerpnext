import frappe

def execute():
    # Ensure 'phone_number' exists in SHG Member and related doctypes
    doctypes = ["SHG Member", "SHG Contribution", "SHG Loan"]

    for dt in doctypes:
        if not frappe.db.has_column(dt, "phone_number"):
            frappe.db.add_column(dt, "phone_number", "varchar(140)")
            frappe.logger().info(f"Added 'phone_number' column to {dt}")

    frappe.db.commit()