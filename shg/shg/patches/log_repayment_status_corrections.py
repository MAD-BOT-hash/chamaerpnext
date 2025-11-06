import frappe

def execute():
    """Patch to add repayment adjustment log functionality."""
    # Reload the SHG Loan doctype to ensure the new fields are available
    frappe.reload_doc("shg", "doctype", "shg_loan")
    frappe.reload_doc("shg", "doctype", "shg_loan_repayment_schedule")
    frappe.reload_doc("shg", "doctype", "repayment_adjustment_log")
    
    # Update existing loan records to ensure they have the new fields
    loans = frappe.get_all("SHG Loan", filters={"docstatus": 1})
    for loan in loans:
        try:
            loan_doc = frappe.get_doc("SHG Loan", loan.name)
            loan_doc.flags.ignore_validate_update_after_submit = True
            loan_doc.save(ignore_permissions=True)
        except Exception:
            pass  # Skip errors to avoid breaking the patch
            
    frappe.db.commit()