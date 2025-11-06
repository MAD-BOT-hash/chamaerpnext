import frappe

def execute():
    """Add SHG Repayment Installment Adjustment doctype and update SHG Loan Repayment doctype."""
    
    # Check if the doctype already exists
    if not frappe.db.exists("DocType", "SHG Repayment Installment Adjustment"):
        # Create the doctype
        frappe.reload_doc("shg", "doctype", "shg_repayment_installment_adjustment")
        frappe.logger().info("Created SHG Repayment Installment Adjustment doctype")
    
    # Reload SHG Loan Repayment doctype to include the new child table field
    frappe.reload_doc("shg", "doctype", "shg_loan_repayment")
    frappe.logger().info("Updated SHG Loan Repayment doctype with installment adjustment field")
    
    # Update existing SHG Loan Repayment Schedule records to ensure total_due is computed correctly
    frappe.db.sql("""
        UPDATE `tabSHG Loan Repayment Schedule` 
        SET total_due = COALESCE(principal_component, 0) + COALESCE(interest_component, 0)
        WHERE (total_due IS NULL OR total_due = 0) 
        AND (principal_component IS NOT NULL OR interest_component IS NOT NULL)
    """)
    frappe.logger().info("Updated SHG Loan Repayment Schedule records with total_due values")
    
    frappe.db.commit()