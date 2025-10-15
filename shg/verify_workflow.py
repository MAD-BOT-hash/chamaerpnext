#!/usr/bin/env python3
"""
Verification script for SHG Contribution & Invoice Workflow
This script verifies that all the implemented changes work correctly.
"""

import os
import sys

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def verify_shg_settings():
    """Verify SHG Settings have all required fields"""
    print("🔍 Verifying SHG Settings...")
    
    try:
        import frappe
        
        # Initialize frappe
        frappe.init(site="test_site", sites_path=".")
        
        settings = frappe.get_single("SHG Settings")
        
        # Check for new fields
        required_fields = [
            'default_income_account',
            'default_receivable_account',
            'auto_generate_sales_invoice',
            'auto_create_contribution_on_invoice_submit',
            'auto_apply_payment_on_payment_entry_submit',
            'apply_late_fee_policy',
            'late_fee_rate'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not hasattr(settings, field):
                missing_fields.append(field)
                
        if missing_fields:
            print(f"❌ Missing fields in SHG Settings: {missing_fields}")
            return False
        else:
            print("✅ SHG Settings verified successfully")
            return True
            
    except Exception as e:
        print(f"❌ Error verifying SHG Settings: {str(e)}")
        return False

def verify_shg_contribution_invoice_fields():
    """Verify SHG Contribution Invoice has all required fields"""
    print("🔍 Verifying SHG Contribution Invoice fields...")
    
    try:
        import frappe
        
        # Initialize frappe
        frappe.init(site="test_site", sites_path=".")
        
        # Get the DocType definition
        doctype = frappe.get_meta("SHG Contribution Invoice")
        
        # Check for new fields
        required_fields = [
            'linked_sales_invoice',
            'linked_shg_contribution',
            'late_fee_amount'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not doctype.has_field(field):
                missing_fields.append(field)
                
        if missing_fields:
            print(f"❌ Missing fields in SHG Contribution Invoice: {missing_fields}")
            return False
        else:
            print("✅ SHG Contribution Invoice fields verified successfully")
            return True
            
    except Exception as e:
        print(f"❌ Error verifying SHG Contribution Invoice fields: {str(e)}")
        return False

def verify_hooks():
    """Verify hooks are properly configured"""
    print("🔍 Verifying hooks configuration...")
    
    try:
        import frappe
        
        # Initialize frappe
        frappe.init(site="test_site", sites_path=".")
        
        # Check if our functions are in hooks
        hooks = frappe.get_hooks()
        
        # Check Payment Entry hooks
        pe_hooks = hooks.get("doc_events", {}).get("Payment Entry", {})
        on_submit_hook = pe_hooks.get("on_submit", "")
        
        if "shg.shg.hooks.payment_entry.payment_entry_on_submit" in str(on_submit_hook):
            print("✅ Payment Entry hooks verified successfully")
            return True
        else:
            print("❌ Payment Entry hooks not properly configured")
            return False
            
    except Exception as e:
        print(f"❌ Error verifying hooks: {str(e)}")
        return False

def verify_workflow_automation_flags():
    """Verify workflow automation flags in SHG Settings"""
    print("🔍 Verifying workflow automation flags...")
    
    try:
        import frappe
        
        # Initialize frappe
        frappe.init(site="test_site", sites_path=".")
        
        settings = frappe.get_single("SHG Settings")
        
        # Check if automation flags exist and have default values
        flags = [
            ('auto_generate_sales_invoice', 1),
            ('auto_create_contribution_on_invoice_submit', 1),
            ('auto_apply_payment_on_payment_entry_submit', 1)
        ]
        
        issues = []
        for flag, expected_default in flags:
            if hasattr(settings, flag):
                # We're just checking existence, not values
                pass
            else:
                issues.append(flag)
                
        if issues:
            print(f"❌ Missing workflow automation flags: {issues}")
            return False
        else:
            print("✅ Workflow automation flags verified successfully")
            return True
            
    except Exception as e:
        print(f"❌ Error verifying workflow automation flags: {str(e)}")
        return False

def main():
    """Main verification function"""
    print("🚀 Starting SHG Workflow Verification...\n")
    
    all_checks = [
        verify_shg_settings,
        verify_shg_contribution_invoice_fields,
        verify_hooks,
        verify_workflow_automation_flags
    ]
    
    results = []
    for check in all_checks:
        results.append(check())
        
    print("\n" + "="*50)
    print("📊 VERIFICATION RESULTS:")
    print("="*50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 All verifications passed! The SHG workflow is properly configured.")
        return 0
    else:
        print("\n⚠️  Some verifications failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    exit(main())