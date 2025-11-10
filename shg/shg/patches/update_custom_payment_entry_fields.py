import frappe

def execute():
    """Update custom field references from Payment Entry to SHG Payment Entry."""
    
    # Update custom fields that reference Payment Entry
    custom_fields = frappe.get_all("Custom Field", 
        filters={"dt": "Payment Entry"},
        fields=["name", "fieldname", "label", "fieldtype", "options"])
    
    for field in custom_fields:
        try:
            # Create equivalent custom field for SHG Payment Entry
            new_field = frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "SHG Payment Entry",
                "fieldname": field.fieldname,
                "label": field.label,
                "fieldtype": field.fieldtype,
                "options": field.options,
                "insert_after": "remarks"  # Add after remarks field
            })
            new_field.insert(ignore_permissions=True)
            
        except Exception as e:
            # Log error but continue
            frappe.log_error(f"Failed to create custom field for SHG Payment Entry: {str(e)}")
    
    frappe.db.commit()
    frappe.msgprint("✅ Updated custom field references for SHG Payment Entry")