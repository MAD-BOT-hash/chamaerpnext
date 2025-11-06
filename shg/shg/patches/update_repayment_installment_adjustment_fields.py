import frappe

def execute():
    """Update SHG Repayment Installment Adjustment doctype with principal_amount and interest_amount fields."""
    
    # Reload the doctype to include the new fields
    frappe.reload_doc("shg", "doctype", "shg_repayment_installment_adjustment")
    frappe.logger().info("Updated SHG Repayment Installment Adjustment doctype with principal_amount and interest_amount fields")
    
    # Reload SHG Loan Repayment doctype to ensure proper linking
    frappe.reload_doc("shg", "doctype", "shg_loan_repayment")
    frappe.logger().info("Updated SHG Loan Repayment doctype")
    
    frappe.db.commit()