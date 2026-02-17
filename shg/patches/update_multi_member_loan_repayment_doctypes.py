import frappe

def execute():
    """Add missing fields to SHG Multi Member Loan Repayment doctype"""
    try:
        # Reload the doctype to ensure all fields are registered
        frappe.reload_doc("shg", "doctype", "shg_multi_member_loan_repayment")
        frappe.reload_doc("shg", "doctype", "shg_multi_member_loan_repayment_item")
        
        # Check if the columns exist, if not add them
        if not frappe.db.has_column("SHG Multi Member Loan Repayment", "total_selected_loans"):
            frappe.db.sql("""
                ALTER TABLE `tabSHG Multi Member Loan Repayment` 
                ADD COLUMN `total_selected_loans` INT DEFAULT 0
            """)
        
        if not frappe.db.has_column("SHG Multi Member Loan Repayment Item", "loan_balance"):
            frappe.db.sql("""
                ALTER TABLE `tabSHG Multi Member Loan Repayment Item` 
                ADD COLUMN `loan_balance` DECIMAL(21,9) DEFAULT 0.000000000
            """)
        
        if not frappe.db.has_column("SHG Multi Member Loan Repayment Item", "status"):
            frappe.db.sql("""
                ALTER TABLE `tabSHG Multi Member Loan Repayment Item` 
                ADD COLUMN `status` VARCHAR(255)
            """)
        
        frappe.db.commit()
        print("Successfully updated SHG Multi Member Loan Repayment doctypes")
    except Exception as e:
        frappe.log_error(f"Error updating doctypes: {str(e)}")
        raise