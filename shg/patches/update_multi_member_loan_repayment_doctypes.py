import frappe

def execute():
    """Add missing fields to SHG Multi Member Loan Repayment doctype"""
    try:
        # Reload the doctype to ensure all fields are registered
        frappe.reload_doc("shg", "doctype", "shg_multi_member_loan_repayment")
        frappe.reload_doc("shg", "doctype", "shg_multi_member_loan_repayment_item")
        
        # Check if the columns exist, if not add them
        if not frappe.db.has_column("SHG Multi Member Loan Repayment", "total_selected_loans"):
            frappe.db.add_column(
                "SHG Multi Member Loan Repayment",
                "total_selected_loans",
                "int"
            )
        
        if not frappe.db.has_column("SHG Multi Member Loan Repayment Item", "status"):
            frappe.db.add_column(
                "SHG Multi Member Loan Repayment Item",
                "status",
                "varchar(255)"
            )
        
        frappe.db.commit()
        print("Successfully updated SHG Multi Member Loan Repayment doctypes")
    except Exception as e:
        frappe.log_error(f"Error updating doctypes: {str(e)}")
        raise