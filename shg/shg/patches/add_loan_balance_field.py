import frappe

def execute():
    """Add loan_balance field to SHG Loan doctype."""
    # This patch ensures the loan_balance field is properly added to the SHG Loan doctype
    # The field should have been added via the JSON file, but this ensures it exists
    
    try:
        # Check if the field already exists
        existing_field = frappe.db.exists("DocField", {
            "parent": "SHG Loan",
            "fieldname": "loan_balance"
        })
        
        if not existing_field:
            # Add the field if it doesn't exist
            frappe.get_doc({
                "doctype": "DocField",
                "parent": "SHG Loan",
                "parenttype": "DocType",
                "parentfield": "fields",
                "fieldname": "loan_balance",
                "fieldtype": "Currency",
                "label": "Loan Balance",
                "precision": 2,
                "read_only": 1,
                "allow_on_submit": 1
            }).insert(ignore_permissions=True)
            
            frappe.msgprint("Added loan_balance field to SHG Loan doctype")
        else:
            frappe.msgprint("loan_balance field already exists in SHG Loan doctype")
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to add loan_balance field to SHG Loan doctype")
        
    # Update existing loans to populate the loan_balance field
    try:
        loans = frappe.get_all("SHG Loan", filters={"docstatus": 1})
        updated_count = 0
        
        for loan in loans:
            try:
                loan_doc = frappe.get_doc("SHG Loan", loan.name)
                # Update the loan balance
                from shg.shg.doctype.shg_loan.shg_loan import get_loan_balance
                loan_doc.loan_balance = get_loan_balance(loan.name)
                loan_doc.flags.ignore_validate_update_after_submit = True
                loan_doc.save(ignore_permissions=True)
                updated_count += 1
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"Failed to update loan balance for {loan.name}")
                
        frappe.msgprint(f"Updated loan balance for {updated_count} loans")
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to update existing loans with loan_balance")