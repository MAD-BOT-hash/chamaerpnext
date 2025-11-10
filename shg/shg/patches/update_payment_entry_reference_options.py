import frappe

def execute():
    """Update SHG Payment Entry Reference doctype to include SHG Loan and SHG Loan Repayment options."""
    
    # Update the reference_doctype field options in SHG Payment Entry Reference
    try:
        # Get the SHG Payment Entry Reference doctype
        doctype = frappe.get_doc("DocType", "SHG Payment Entry Reference")
        
        # Find the reference_doctype field
        for field in doctype.fields:
            if field.fieldname == "reference_doctype":
                # Update the options to include SHG Loan and SHG Loan Repayment
                field.options = "Sales Invoice\nJournal Entry\nSHG Loan\nSHG Loan Repayment"
                break
        
        # Save the doctype
        doctype.save(ignore_permissions=True)
        frappe.db.commit()
        
        frappe.msgprint("✅ Updated SHG Payment Entry Reference options successfully")
        
    except Exception as e:
        frappe.log_error(f"Failed to update SHG Payment Entry Reference options: {str(e)}")
        frappe.msgprint(f"Failed to update SHG Payment Entry Reference options: {str(e)}")