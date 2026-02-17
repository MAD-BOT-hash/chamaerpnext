import frappe

def execute():
    """Add loan_balance field to SHG Multi Member Loan Repayment Item table"""
    try:
        # Check if the loan_balance column already exists
        if not frappe.db.has_column("SHG Multi Member Loan Repayment Item", "loan_balance"):
            # Add the loan_balance column
            frappe.db.add_column(
                "SHG Multi Member Loan Repayment Item",
                "loan_balance",
                "Currency"
            )
            frappe.db.commit()
            print("Successfully added 'loan_balance' column to SHG Multi Member Loan Repayment Item table")
        else:
            print("'loan_balance' column already exists in SHG Multi Member Loan Repayment Item table")
        
        # Also make sure the status column exists (in case it wasn't added previously)
        if not frappe.db.has_column("SHG Multi Member Loan Repayment Item", "status"):
            frappe.db.add_column(
                "SHG Multi Member Loan Repayment Item",
                "status",
                "varchar(255)"
            )
            frappe.db.commit()
            print("Successfully added 'status' column to SHG Multi Member Loan Repayment Item table")
        
    except Exception as e:
        frappe.log_error(f"Error adding loan_balance column: {str(e)}")
        raise