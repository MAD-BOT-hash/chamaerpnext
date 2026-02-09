import frappe

def execute():
    """Add status field to SHG Multi Member Loan Repayment Item table"""
    try:
        # Check if the column already exists
        if not frappe.db.has_column("SHG Multi Member Loan Repayment Item", "status"):
            # Add the status column
            frappe.db.add_column(
                "SHG Multi Member Loan Repayment Item",
                "status",
                "varchar(255)"
            )
            frappe.db.commit()
            print("Successfully added 'status' column to SHG Multi Member Loan Repayment Item table")
        else:
            print("'status' column already exists in SHG Multi Member Loan Repayment Item table")
    except Exception as e:
        frappe.log_error(f"Error adding status column: {str(e)}")
        raise