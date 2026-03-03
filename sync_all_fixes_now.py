"""
Immediate sync script for all defensive fixes.
Run this to apply all fixes without waiting for migration.
"""
import frappe
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def sync_all_fixes():
    """Synchronize all fixes immediately"""
    try:
        print("="*70)
        print("🔧 SHG ERPNext - Synchronizing All Defensive Fixes")
        print("="*70)
        
        frappe.init(site='.')
        frappe.connect()
        
        # Run the patches directly
        print("\n1️⃣ Running: remove_invalid_company_default")
        from shg.shg.patches.remove_invalid_company_default import execute as fix_company
        fix_company()
        
        print("\n2️⃣ Running: sync_defensive_invoice_total_fixes")
        from shg.shg.patches.sync_defensive_invoice_total_fixes import execute as sync_fixes
        sync_fixes()
        
        print("\n" + "="*70)
        print("✅ ALL FIXES SYNCHRONIZED SUCCESSFULLY!")
        print("="*70)
        print("\n📋 SUMMARY OF FIXES APPLIED:")
        print("   • Company field default fixed (removed Python expression)")
        print("   • Invoice total field access made defensive (grand_total → amount fallback)")
        print("   • All caches cleared and DocTypes reloaded")
        print("   • Phone validation made flexible (07XX, 01XX, +254 formats)")
        print("   • Company field made editable after submit")
        print("\n⚠️  IMPORTANT:")
        print("   You MUST restart bench for changes to take effect:")
        print("   bench restart")
        print("\n🔄 Then clear browser cache:")
        print("   Ctrl+Shift+Delete → Clear cached images and files")
        print("\n🔄 Then hard reload:")
        print("   Ctrl+Shift+R")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        frappe.db.rollback()
    finally:
        frappe.destroy()

if __name__ == "__main__":
    sync_all_fixes()