import frappe

def execute():
    """Add 'Get Active Members' functionality to SHG Loan doctype."""
    # Reload the SHG Loan doctype to include the new method
    frappe.reload_doc("shg", "doctype", "shg_loan")
    
    # Reload the SHG Loan JavaScript file
    frappe.reload_doc("shg", "doctype", "shg_loan", force=True)
    
    frappe.logger().info("Added 'Get Active Members' functionality to SHG Loan doctype")