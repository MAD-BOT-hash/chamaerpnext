"""
Complete fix script for invalid Company field default in SHG Member
This script clears caches and fixes the database directly
"""
import frappe
import sys
import os

# Add the app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def fix_company_field_complete():
    """Complete fix including cache clearing"""
    try:
        print("🔧 Starting complete fix for invalid Company field default...")
        
        # Initialize frappe
        frappe.init(site='.')
        frappe.connect()
        
        doctype = "SHG Member"
        fieldname = "company"
        
        # Fix 1: Clear DocType cache first
        print("\n1️⃣ Clearing DocType cache...")
        frappe.clear_cache(doctype=doctype)
        frappe.clear_doctype_cache(doctype)
        print("   ✅ DocType cache cleared")
        
        # Fix 2: Update Custom Field if it exists
        print("\n2️⃣ Checking Custom Field...")
        custom_field_name = f"{doctype}-{fieldname}"
        if frappe.db.exists("Custom Field", custom_field_name):
            frappe.db.set_value("Custom Field", custom_field_name, "default", "")
            frappe.db.commit()
            print(f"   ✅ Removed invalid default from Custom Field: {custom_field_name}")
        else:
            print("   ℹ️ No Custom Field override found")
        
        # Fix 3: Update DocType field directly using SQL (more reliable)
        print("\n3️⃣ Updating DocType field definition...")
        
        # Check current value
        current_default = frappe.db.sql("""
            SELECT `default` FROM `tabDocField`
            WHERE parent = %s AND fieldname = %s
        """, (doctype, fieldname), as_dict=True)
        
        if current_default and current_default[0].get('default') == 'frappe.defaults.get_user_default("Company")':
            # Update using SQL to bypass any caching issues
            frappe.db.sql("""
                UPDATE `tabDocField`
                SET `default` = ''
                WHERE parent = %s AND fieldname = %s
            """, (doctype, fieldname))
            frappe.db.commit()
            print(f"   ✅ Removed invalid default from DocType Field via SQL")
        else:
            print(f"   ℹ️ Current default: {current_default[0].get('default') if current_default else 'None'}")
        
        # Also update via DocType document for consistency
        if frappe.db.exists("DocType", doctype):
            try:
                doc = frappe.get_doc("DocType", doctype)
                field_updated = False
                
                for field in doc.fields:
                    if field.fieldname == fieldname:
                        if field.default == 'frappe.defaults.get_user_default("Company")':
                            field.default = ""
                            field_updated = True
                            print(f"   ✅ Updated field via DocType document")
                        break
                
                if field_updated:
                    doc.save(ignore_permissions=True)
                    frappe.db.commit()
            except Exception as e:
                print(f"   ⚠️ DocType document update skipped: {e}")
        
        # Fix 4: Clear invalid values from existing records
        print("\n4️⃣ Fixing existing records...")
        result = frappe.db.sql("""
            UPDATE `tabSHG Member`
            SET company = NULL
            WHERE company = 'frappe.defaults.get_user_default("Company")'
        """)
        
        if result:
            frappe.db.commit()
            print(f"   ✅ Cleared invalid company value from {result} existing records")
        else:
            print("   ℹ️ No existing records with invalid company value found")
        
        # Fix 5: Clear all caches again
        print("\n5️⃣ Clearing all caches...")
        frappe.clear_cache()
        frappe.cache().flushall()
        print("   ✅ All caches cleared")
        
        # Fix 6: Reload DocType
        print("\n6️⃣ Reloading DocType...")
        frappe.reload_doc('shg', 'doctype', 'shg_member', force=True)
        print("   ✅ DocType reloaded")
        
        print("\n" + "="*60)
        print("🎉 FIX COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nIMPORTANT NEXT STEPS:")
        print("1. 🔄 Restart your Frappe bench:")
        print("   bench restart")
        print("\n2. 🧹 Clear browser cache completely:")
        print("   - Press Ctrl+Shift+Delete")
        print("   - Select 'Cached images and files'")
        print("   - Click Clear")
        print("\n3. 🔄 Hard reload the page:")
        print("   - Press Ctrl+Shift+R")
        print("\n4. ✅ Verify the fix:")
        print("   - Open SHG Member form")
        print("   - Company field should be EMPTY (not showing Python code)")
        print("   - Server will auto-populate company when you save")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        frappe.db.rollback()
    finally:
        frappe.destroy()

if __name__ == "__main__":
    fix_company_field_complete()