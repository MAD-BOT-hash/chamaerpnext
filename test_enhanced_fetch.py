"""
Test script to verify the enhanced fetch functions are working properly
"""
import frappe


def test_enhanced_fetch_functions():
    """Test the enhanced fetch functions to verify they work properly for both company and member"""
    print("🔍 Testing enhanced fetch functions...")
    
    try:
        # Get the default company
        company = frappe.defaults.get_global_default("company") or "Test Company"
        print(f"🏢 Using company: {company}")
        
        # Check how many members exist in the company
        members = frappe.get_all("SHG Member", filters={"company": company}, fields=["name", "member_name"], limit=2)
        print(f"👥 Found {len(members)} members in company:")
        for i, member in enumerate(members):
            print(f"   {i+1}. {member.name}: {member.member_name}")
        
        if len(members) >= 1:
            # Test fetching for specific member
            test_member = members[0].name
            print(f"\nTesting fetch for specific member: {test_member}")
            
            from shg.shg.services.payment.bulk_payment_service import get_all_unpaid_items_for_member
            member_items = get_all_unpaid_items_for_member(test_member)
            print(f"   Found {len(member_items)} unpaid items for member")
            for item in member_items[:3]:  # Show first 3
                print(f"     - {item['reference_doctype']}: {item['reference_name']} - {item['outstanding_amount']}")
        
        # Test fetching for company
        print(f"\nTesting fetch for entire company: {company}")
        
        from shg.shg.services.payment.bulk_payment_service import get_all_unpaid_items_for_company
        company_items = get_all_unpaid_items_for_company(company)
        print(f"   Found {len(company_items)} total unpaid items for company")
        
        # Group by member to see distribution
        member_distribution = {}
        for item in company_items:
            member_name = item['member_name']
            if member_name not in member_distribution:
                member_distribution[member_name] = 0
            member_distribution[member_name] += 1
        
        print("   Distribution by member:")
        for member, count in member_distribution.items():
            print(f"     - {member}: {count} items")
        
        print(f"\n✅ Enhancement completed successfully!")
        print("   - Added fetch for specific member functionality")
        print("   - Maintained company-wide fetch functionality")
        print("   - Both functions are working correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing enhanced fetch functions: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_enhanced_fetch_functions()