import frappe
import os

def execute():
    """Recreate SHG Loan Repayment doctype with new implementation."""
    
    # Rename old files
    rename_old_files()
    
    # Rename new files to active names
    rename_new_files()
    
    frappe.msgprint("✅ SHG Loan Repayment doctype recreated with new implementation")

def rename_old_files():
    """Rename old files with .bak extension."""
    doctype_path = frappe.get_app_path("shg", "shg", "doctype", "shg_loan_repayment")
    
    files_to_rename = [
        "shg_loan_repayment.json",
        "shg_loan_repayment.py",
        "shg_loan_repayment.js"
    ]
    
    for filename in files_to_rename:
        old_path = os.path.join(doctype_path, filename)
        new_path = os.path.join(doctype_path, filename + ".bak")
        
        if os.path.exists(old_path):
            os.rename(old_path, new_path)
            frappe.msgprint(f"Renamed {filename} to {filename}.bak")

def rename_new_files():
    """Rename new files to active names."""
    doctype_path = frappe.get_app_path("shg", "shg", "doctype", "shg_loan_repayment")
    
    files_to_rename = [
        "shg_loan_repayment_new.json",
        "shg_loan_repayment_new.py",
        "shg_loan_repayment_new.js"
    ]
    
    target_names = [
        "shg_loan_repayment.json",
        "shg_loan_repayment.py",
        "shg_loan_repayment.js"
    ]
    
    for i, filename in enumerate(files_to_rename):
        old_path = os.path.join(doctype_path, filename)
        new_path = os.path.join(doctype_path, target_names[i])
        
        if os.path.exists(old_path):
            os.rename(old_path, new_path)
            frappe.msgprint(f"Renamed {filename} to {target_names[i]}")