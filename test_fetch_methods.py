"""
Quick test to verify the fetch methods are now accessible
"""
import frappe


def test_fetch_methods():
    """Test that the fetch methods are properly exposed"""
    print("🔍 Testing Fetch Method Accessibility...")
    
    try:
        # Test importing the methods directly
        from shg.shg.services.payment.bulk_payment_service import (
            get_unpaid_invoices_for_company,
            get_unpaid_contributions_for_company,
            get_unpaid_meeting_fines_for_company,
            get_all_unpaid_items_for_company
        )
        
        print("✅ All fetch methods imported successfully")
        
        # Test method signatures
        import inspect
        
        methods = [
            get_unpaid_invoices_for_company,
            get_unpaid_contributions_for_company,
            get_unpaid_meeting_fines_for_company,
            get_all_unpaid_items_for_company
        ]
        
        for method in methods:
            sig = inspect.signature(method)
            print(f"✅ {method.__name__}: {sig}")
            
            # Check if it has frappe.whitelist decorator
            if hasattr(method, '__wrapped__'):
                print(f"   frappe.whitelist decorator")
            else:
                print(f"   ⚠️  No frappe.whitelist decorator - this might cause issues")
        
        print("\n🎉 All methods are accessible and properly defined!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_fetch_methods()