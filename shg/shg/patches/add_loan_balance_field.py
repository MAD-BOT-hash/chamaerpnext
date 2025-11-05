import frappe
from frappe.database.schema import add_column

def execute():
    """Add loan_balance field to SHG Loan doctype if it doesn't exist."""
    
    # Check if loan_balance column exists in the database
    if not frappe.db.has_column("SHG Loan", "loan_balance"):
        # Add the column to the database table
        add_column("SHG Loan", "loan_balance", "Currency", precision=2)
        frappe.logger().info("Added loan_balance column to SHG Loan doctype")
    
    frappe.db.commit()

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