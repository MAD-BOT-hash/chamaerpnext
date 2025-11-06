import frappe

def execute():
    """Add generate_individual_loans function to SHG Loan doctype."""
    # Reload the SHG Loan doctype to include the new method
    frappe.reload_doc("shg", "doctype", "shg_loan")
    
    frappe.logger().info("Added generate_individual_loans function to SHG Loan doctype")