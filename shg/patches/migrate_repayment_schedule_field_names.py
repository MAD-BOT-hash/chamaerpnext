import frappe

def execute():
    """Migrate repayment schedule field names from old format to new format."""
    
    # Check if the doctype exists
    if not frappe.db.exists("DocType", "SHG Loan Repayment Schedule"):
        print("SHG Loan Repayment Schedule doctype not found")
        return
    
    # Check if old fields exist (this would be during an upgrade)
    old_fields_exist = (
        frappe.db.exists("DocField", {"parent": "SHG Loan Repayment Schedule", "fieldname": "principal_component"}) or
        frappe.db.exists("DocField", {"parent": "SHG Loan Repayment Schedule", "fieldname": "interest_component"})
    )
    
    if not old_fields_exist:
        print("Old field names not found in SHG Loan Repayment Schedule - migration not needed")
        return
    
    # Check if new fields exist
    new_fields_exist = (
        frappe.db.exists("DocField", {"parent": "SHG Loan Repayment Schedule", "fieldname": "principal_amount"}) and
        frappe.db.exists("DocField", {"parent": "SHG Loan Repayment Schedule", "fieldname": "interest_amount"})
    )
    
    if not new_fields_exist:
        print("New field names not found in SHG Loan Repayment Schedule - cannot migrate")
        return
    
    # Migrate data from old fields to new fields
    print("Migrating repayment schedule field names...")
    
    # Update all existing repayment schedule records
    # Note: This assumes the old fields still exist in the database during migration
    frappe.db.sql("""
        UPDATE `tabSHG Loan Repayment Schedule` 
        SET principal_amount = principal_component,
            interest_amount = interest_component
        WHERE (principal_component IS NOT NULL OR interest_component IS NOT NULL)
    """)
    
    print("Repayment schedule field names migration completed")
    
    # Note: The actual removal of old fields should be done in a separate patch
    # after confirming the data migration was successful