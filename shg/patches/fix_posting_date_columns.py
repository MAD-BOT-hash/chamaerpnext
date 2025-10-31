import frappe
from frappe.model.utils.rename_field import rename_field
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def execute():
    """Ensure posting_date columns exist in database tables for SHG transactional doctypes"""
    
    # List of doctypes that need posting_date field
    doctypes = ["SHG Loan", "SHG Contribution", "SHG Loan Repayment"]
    
    for doctype in doctypes:
        try:
            # Check if the column exists in the database table
            if not frappe.db.has_column(doctype, 'posting_date'):
                # Add the column directly to the database table
                frappe.db.sql(f"""
                    ALTER TABLE `tab{doctype}` 
                    ADD COLUMN IF NOT EXISTS `posting_date` DATE NOT NULL DEFAULT CURRENT_DATE 
                    AFTER `member`
                """)
                frappe.db.commit()
                print(f"Added posting_date column to database table for {doctype}")
            else:
                print(f"posting_date column already exists in database table for {doctype}")
                
        except Exception as e:
            print(f"Error adding posting_date column to {doctype}: {str(e)}")
            
    # Reload doctypes to ensure schema is in sync
    for doctype in doctypes:
        try:
            frappe.reload_doc("shg", "doctype", frappe.scrub(doctype))
            print(f"Reloaded doctype {doctype}")
        except Exception as e:
            print(f"Error reloading doctype {doctype}: {str(e)}")