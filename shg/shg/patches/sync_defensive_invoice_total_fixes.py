"""
Patch to ensure all defensive invoice total field fixes are synchronized.
This patch clears caches and reloads all affected DocTypes to ensure code changes take effect.
"""
import frappe

def execute():
    """Synchronize all defensive invoice total field fixes"""
    try:
        print("[SHG Patch] Synchronizing defensive invoice total field fixes...")
        
        # List of all DocTypes that need cache clearing and reloading
        affected_doctypes = [
            "SHG Member",
            "SHG Bulk Payment",
            "SHG Contribution Invoice",
            "SHG Contribution",
            "SHG Meeting Fine",
            "SHG Payment Entry",
            "SHG Loan",
            "SHG Loan Repayment"
        ]
        
        # Clear all caches first
        print("[SHG Patch] Clearing all caches...")
        frappe.clear_cache()
        
        # Clear DocType-specific caches
        for doctype in affected_doctypes:
            try:
                frappe.clear_cache(doctype=doctype)
                frappe.clear_doctype_cache(doctype)
                print(f"[SHG Patch] Cleared cache for {doctype}")
            except Exception as e:
                print(f"[SHG Patch] Warning: Could not clear cache for {doctype}: {e}")
        
        # Reload all affected DocTypes to pick up code changes
        print("[SHG Patch] Reloading affected DocTypes...")
        doctype_modules = {
            "SHG Member": "shg.shg.doctype.shg_member.shg_member",
            "SHG Bulk Payment": "shg.shg.doctype.shg_bulk_payment.shg_bulk_payment",
            "SHG Contribution Invoice": "shg.shg.doctype.shg_contribution_invoice.shg_contribution_invoice",
            "SHG Contribution": "shg.shg.doctype.shg_contribution.shg_contribution",
            "SHG Meeting Fine": "shg.shg.doctype.shg_meeting_fine.shg_meeting_fine",
            "SHG Payment Entry": "shg.shg.doctype.shg_payment_entry.shg_payment_entry",
        }
        
        for doctype, module_path in doctype_modules.items():
            try:
                if frappe.db.exists("DocType", doctype):
                    frappe.reload_doc('shg', 'doctype', doctype.lower().replace(' ', '_'), force=True)
                    print(f"[SHG Patch] Reloaded {doctype}")
            except Exception as e:
                print(f"[SHG Patch] Warning: Could not reload {doctype}: {e}")
        
        # Clear redis cache completely
        try:
            frappe.cache().flushall()
            print("[SHG Patch] Flushed Redis cache")
        except Exception as e:
            print(f"[SHG Patch] Warning: Could not flush Redis cache: {e}")
        
        # Log success
        frappe.db.commit()
        print("[SHG Patch] Successfully synchronized all defensive invoice total field fixes")
        print("[SHG Patch] Changes will take effect after bench restart")
        
    except Exception as e:
        frappe.log_error(f"Error synchronizing defensive fixes: {str(e)}", "SHG Patch Error")
        print(f"[SHG Patch Error] {str(e)}")
        raise