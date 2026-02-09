import frappe

def execute():
    """Register the Multi Member Loan Repayment doctypes"""
    
    # Reload the parent doctype
    frappe.reload_doc("shg", "doctype", "shg_multi_member_loan_repayment")
    
    # Reload the child table doctype
    frappe.reload_doc("shg", "doctype", "shg_multi_member_loan_repayment_item")
    
    frappe.db.commit()
    
    frappe.msgprint("Multi Member Loan Repayment doctypes registered successfully")