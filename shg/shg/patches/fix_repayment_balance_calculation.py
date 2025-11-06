import frappe

def execute():
    """Fix repayment balance calculation to include principal and interest."""
    # Reload the SHG Loan doctype to include the new method
    frappe.reload_doc("shg", "doctype", "shg_loan")
    
    # Reload the SHG Loan Repayment doctype
    frappe.reload_doc("shg", "doctype", "shg_loan_repayment")
    
    frappe.logger().info("Fixed repayment balance calculation to include principal and interest")