import frappe

def execute():
    """Add disbursed_on field to SHG Loan doctype if it doesn't exist."""
    
    # Check if the field already exists
    if not frappe.db.exists("Custom Field", {"dt": "SHG Loan", "fieldname": "disbursed_on"}):
        # Create the custom field
        custom_field = frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "SHG Loan",
            "fieldname": "disbursed_on",
            "label": "Disbursed On",
            "fieldtype": "Datetime",
            "insert_after": "disbursement_date",
            "read_only": 1,
            "allow_on_submit": 1
        })
        custom_field.insert(ignore_permissions=True)
        frappe.msgprint("Added 'Disbursed On' field to SHG Loan doctype")
    
    # Update existing loans to set disbursed_on where status is Disbursed
    frappe.db.sql("""
        UPDATE `tabSHG Loan` 
        SET disbursed_on = disbursement_date 
        WHERE status = 'Disbursed' AND disbursed_on IS NULL AND disbursement_date IS NOT NULL
    """)
    
    frappe.msgprint("Updated existing loans with disbursed_on timestamp")