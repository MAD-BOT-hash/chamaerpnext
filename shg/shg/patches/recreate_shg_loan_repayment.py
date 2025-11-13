import frappe
import os

def execute():
    """Clean up old SHG Loan Repayment New files."""
    
    # Remove old new files that are no longer needed
    remove_old_new_files()
    
    frappe.msgprint("✅ Old SHG Loan Repayment New files removed")

def remove_old_new_files():
    """Remove old new files that are no longer needed."""
    doctype_path = "c:/Users/user/Downloads/shg-erpnext/shg/shg/doctype/shg_loan_repayment"
    
    files_to_remove = [
        "shg_loan_repayment_new.json",
        "shg_loan_repayment_new.py",
        "shg_loan_repayment_new.js"
    ]
    
    for filename in files_to_remove:
        file_path = os.path.join(doctype_path, filename)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            frappe.msgprint(f"Removed {filename}")