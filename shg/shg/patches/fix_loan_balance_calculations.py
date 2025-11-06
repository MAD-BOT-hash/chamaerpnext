import frappe

def execute():
    """Fix loan balance calculations to include principal and interest."""
    # Reload the SHG Loan doctype to include the new methods
    frappe.reload_doc("shg", "doctype", "shg_loan")
    
    # Reload the SHG Loan Repayment doctype
    frappe.reload_doc("shg", "doctype", "shg_loan_repayment")
    
    # Update all existing loans to recalculate balances
    loans = frappe.get_all("SHG Loan", filters={"docstatus": 1}, fields=["name"])
    for loan in loans:
        try:
            # Update loan summary
            from shg.shg.doctype.shg_loan.shg_loan import update_loan_summary
            update_loan_summary(loan.name)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to update loan summary for {loan.name}")
    
    frappe.logger().info("Fixed loan balance calculations to include principal and interest")