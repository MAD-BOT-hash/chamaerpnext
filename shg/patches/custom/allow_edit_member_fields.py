import frappe

def execute():
    """Allow specific fields in SHG Member DocType to be editable even after the document is submitted."""
    
    # Fields to enable editing on submit
    fields_to_enable = [
        "membership_date",
        "id_number", 
        "phone_number",
        "email",  # This is the actual fieldname for email_address
        "member_id"
    ]
    
    # Update each field to allow editing on submit
    for fieldname in fields_to_enable:
        # Check if this is a standard field (in the doctype JSON) or a custom field
        field_exists = frappe.db.exists("DocField", {
            "parent": "SHG Member",
            "fieldname": fieldname
        })
        
        if field_exists:
            # For standard fields, we need to update the JSON file directly
            # But we can also set the allow_on_submit property via Property Setter
            if not frappe.db.exists("Property Setter", {
                "doc_type": "SHG Member",
                "field_name": fieldname,
                "property": "allow_on_submit"
            }):
                property_setter = frappe.get_doc({
                    "doctype": "Property Setter",
                    "doc_type": "SHG Member",
                    "field_name": fieldname,
                    "property": "allow_on_submit",
                    "value": "1",
                    "property_type": "Check"
                })
                property_setter.insert(ignore_permissions=True)
                frappe.db.commit()
                print(f"Enabled editing on submit for standard field: {fieldname}")
        else:
            # For custom fields, update directly
            frappe.db.set_value(
                "Custom Field",
                {"dt": "SHG Member", "fieldname": fieldname},
                "allow_on_submit",
                1
            )
            frappe.db.commit()
            print(f"Enabled editing on submit for custom field: {fieldname}")
    
    # Special handling for member_id which is read_only
    # We need to make it editable on submit but it's currently read_only
    if not frappe.db.exists("Property Setter", {
        "doc_type": "SHG Member",
        "field_name": "member_id",
        "property": "read_only"
    }):
        property_setter = frappe.get_doc({
            "doctype": "Property Setter",
            "doc_type": "SHG Member",
            "field_name": "member_id",
            "property": "read_only",
            "value": "0",
            "property_type": "Check"
        })
        property_setter.insert(ignore_permissions=True)
        frappe.db.commit()
        print("Made member_id field editable (removed read_only)")
    
    frappe.msgprint("Enabled editing on submit for key SHG Member fields.")