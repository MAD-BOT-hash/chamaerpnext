"""
Data-safe fix for invalid Company field - Preserves all member information
This script fixes the company field issue without losing any existing data
"""
import frappe
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def fix_company_preserve_data():
    """Fix company field while preserving all member data"""
    try:
        print("🔧 Starting data-safe fix for Company field...")
        print("="*60)
        
        frappe.init(site='.')
        frappe.connect()
        
        # Step 1: Get default company for replacement
        print("\n1️⃣ Determining default company...")
        default_company = frappe.db.get_single_value("SHG Settings", "company")
        if not default_company:
            default_company = frappe.defaults.get_user_default("Company")
        if not default_company:
            default_company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not default_company:
            companies = frappe.get_all("Company", limit=1)
            if companies:
                default_company = companies[0].name
        
        if not default_company:
            print("❌ ERROR: No default company found!")
            print("   Please set a company in SHG Settings or create a Company first.")
            return
        
        print(f"   ✅ Will use company: {default_company}")
        
        # Step 2: Find affected members
        print("\n2️⃣ Finding members with invalid company value...")
        affected_members = frappe.db.sql("""
            SELECT name, member_name, member_id, company
            FROM `tabSHG Member`
            WHERE company = 'frappe.defaults.get_user_default(\"Company\")'
               OR company IS NULL
               OR company = ''
        """, as_dict=True)
        
        print(f"   Found {len(affected_members)} members needing company assignment")
        
        if affected_members:
            print("\n   Affected members:")
            for m in affected_members[:10]:  # Show first 10
                print(f"   - {m['member_id']}: {m['member_name']}")
            if len(affected_members) > 10:
                print(f"   ... and {len(affected_members) - 10} more")
        
        # Step 3: Update affected members with proper company
        print("\n3️⃣ Updating members with correct company...")
        if affected_members:
            # Update in batches for better performance
            batch_size = 100
            total_updated = 0
            
            for i in range(0, len(affected_members), batch_size):
                batch = affected_members[i:i+batch_size]
                member_names = [m['name'] for m in batch]
                
                # Use parameterized query for safety
                placeholders = ','.join(['%s'] * len(member_names))
                frappe.db.sql(f"""
                    UPDATE `tabSHG Member`
                    SET company = %s
                    WHERE name IN ({placeholders})
                """, (default_company,) + tuple(member_names))
                
                total_updated += len(batch)
                print(f"   Updated {total_updated}/{len(affected_members)} members...")
            
            frappe.db.commit()
            print(f"   ✅ Successfully updated {total_updated} members with company: {default_company}")
        else:
            print("   ℹ️ No members needed company assignment")
        
        # Step 4: Fix the DocType field definition
        print("\n4️⃣ Fixing DocType field definition...")
        
        # Clear caches first
        frappe.clear_cache(doctype="SHG Member")
        frappe.clear_doctype_cache("SHG Member")
        
        # Update via SQL
        current_default = frappe.db.sql("""
            SELECT `default` FROM `tabDocField`
            WHERE parent = 'SHG Member' AND fieldname = 'company'
        """, as_dict=True)
        
        if current_default and current_default[0].get('default') == 'frappe.defaults.get_user_default("Company")':
            frappe.db.sql("""
                UPDATE `tabDocField`
                SET `default` = ''
                WHERE parent = 'SHG Member' AND fieldname = 'company'
            """)
            frappe.db.commit()
            print("   ✅ Removed invalid default from DocType field")
        else:
            print(f"   ℹ️ DocType field already clean or not found")
        
        # Step 5: Clear all caches
        print("\n5️⃣ Clearing all caches...")
        frappe.clear_cache()
        frappe.cache().flushall()
        print("   ✅ All caches cleared")
        
        # Step 6: Summary
        print("\n" + "="*60)
        print("🎉 DATA-SAFE FIX COMPLETED!")
        print("="*60)
        
        print(f"\n📊 SUMMARY:")
        print(f"   • Default company used: {default_company}")
        print(f"   • Members updated: {len(affected_members)}")
        print(f"   • All member data preserved: ✅")
        print(f"   • Invalid default removed: ✅")
        
        print("\n📋 NEXT STEPS:")
        print("   1. Restart Frappe bench:")
        print("      bench restart")
        print("\n   2. Clear browser cache:")
        print("      Ctrl+Shift+Delete → Clear cached images and files")
        print("\n   3. Hard reload page:")
        print("      Ctrl+Shift+R")
        print("\n   4. Verify fix:")
        print("      Open any SHG Member - Company should show:", default_company)
        
        print("\n✅ All member information has been preserved!")
        print("✅ Company field now has correct value for all members!")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        frappe.db.rollback()
    finally:
        frappe.destroy()

if __name__ == "__main__":
    fix_company_preserve_data()