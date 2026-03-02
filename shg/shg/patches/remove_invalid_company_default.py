"""
Patch to remove invalid Python expression from Company field default in SHG Member
"""
import frappe

def execute():
    """Remove invalid default value from SHG Member Company field"""
    try:
        # Update the Custom Field or DocType Field to remove the invalid default
        doctype = "SHG Member"
        fieldname = "company"
        
        # Check if there's a Custom Field override
        custom_field_name = f"{doctype}-{fieldname}"
        if frappe.db.exists("Custom Field", custom_field_name):
            # Update the custom field to remove the default
            frappe.db.set_value("Custom Field", custom_field_name, "default", "")
            frappe.db.commit()
            print(f"[SHG Patch] Removed invalid default from Custom Field: {custom_field_name}")
        
        # Also check and update the DocType field directly
        if frappe.db.exists("DocType", doctype):
            doc = frappe.get_doc("DocType", doctype)
            field_updated = False
            
            for field in doc.fields:
                if field.fieldname == fieldname:
                    if field.default == 'frappe.defaults.get_user_default("Company")':
                        field.default = ""
                        field_updated = True
                        print(f"[SHG Patch] Removed invalid default from DocType Field: {doctype}.{fieldname}")
                    break
            
            if field_updated:
                doc.save(ignore_permissions=True)
                frappe.db.commit()
        
        # Update any existing documents that have the literal string as company
        # This fixes data corruption from the bug
        affected_count = frappe.db.sql("""
            UPDATE `tabSHG Member`
            SET company = NULL
            WHERE company = 'frappe.defaults.get_user_default("Company")'
        """)
        
        if affected_count:
            frappe.db.commit()
            print(f"[SHG Patch] Cleared invalid company value from {affected_count} existing SHG Member records")
        
        print("[SHG Patch] Successfully removed invalid Company field default")
        
    except Exception as e:
        frappe.log_error(f"Error removing invalid company default: {str(e)}", "SHG Patch Error")
        print(f"[SHG Patch Error] {str(e)}")
        raise