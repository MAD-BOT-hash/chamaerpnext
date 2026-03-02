"""
Immediate fix script for invalid Company field default in SHG Member
Run this script to fix the issue immediately without waiting for migration
"""
import frappe
import sys
import os

# Add the app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def fix_company_field():
    """Fix the invalid company field default immediately"""
    try:
        print("🔧 Fixing invalid Company field default in SHG Member...")
        
        # Initialize frappe
        frappe.init(site='.')
        frappe.connect()
        
        doctype = "SHG Member"
        fieldname = "company"
        
        # Fix 1: Update Custom Field if it exists
        custom_field_name = f"{doctype}-{fieldname}"
        if frappe.db.exists("Custom Field", custom_field_name):
            frappe.db.set_value("Custom Field", custom_field_name, "default", "")
            print(f"✅ Removed invalid default from Custom Field: {custom_field_name}")
        
        # Fix 2: Update DocType field directly
        if frappe.db.exists("DocType", doctype):
            doc = frappe.get_doc("DocType", doctype)
            field_updated = False
            
            for field in doc.fields:
                if field.fieldname == fieldname:
                    if field.default == 'frappe.defaults.get_user_default("Company")':
                        field.default = ""
                        field_updated = True
                        print(f"✅ Removed invalid default from DocType Field: {doctype}.{fieldname}")
                    break
            
            if field_updated:
                doc.save(ignore_permissions=True)
        
        # Fix 3: Clear invalid values from existing records
        result = frappe.db.sql("""
            UPDATE `tabSHG Member`
            SET company = NULL
            WHERE company = 'frappe.defaults.get_user_default("Company")'
        """)
        
        if result:
            print(f"✅ Cleared invalid company value from existing SHG Member records")
        
        frappe.db.commit()
        
        print("\n🎉 Successfully fixed invalid Company field default!")
        print("\nNext steps:")
        print("1. Clear your browser cache (Ctrl+Shift+R)")
        print("2. Reload the SHG Member form")
        print("3. The Company field should now be empty instead of showing the Python code")
        print("4. Server-side logic will auto-populate the company when you save")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        frappe.db.rollback()
    finally:
        frappe.destroy()

if __name__ == "__main__":
    fix_company_field()