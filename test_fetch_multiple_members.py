"""
Test script to verify the fetch functions are working properly
"""
import frappe


def test_fetch_functions():
    """Test the fetch functions to see if they return data for multiple members"""
    print("🔍 Testing fetch functions for multiple members...")
    
    try:
        # Get the default company
        company = frappe.defaults.get_global_default("company") or "Test Company"
        print(f"🏢 Using company: {company}")
        
        # Check how many members exist in the company
        members = frappe.get_all("SHG Member", filters={"company": company}, fields=["name", "member_name"])
        print(f"👥 Found {len(members)} members in company:")
        for member in members:
            print(f"   - {member.name}: {member.member_name}")
        
        # Test fetching unpaid invoices
        from shg.shg.services.payment.bulk_payment_service import get_unpaid_invoices_for_company
        invoices = get_unpaid_invoices_for_company(company)
        print(f"\n📋 Found {len(invoices)} unpaid invoices:")
        for inv in invoices[:5]:  # Show first 5
            print(f"   - {inv['member_name']}: {inv['reference_name']} - {inv['outstanding_amount']}")
        
        # Test fetching unpaid contributions
        from shg.shg.services.payment.bulk_payment_service import get_unpaid_contributions_for_company
        contributions = get_unpaid_contributions_for_company(company)
        print(f"\n💰 Found {len(contributions)} unpaid contributions:")
        for contrib in contributions[:5]:  # Show first 5
            print(f"   - {contrib['member_name']}: {contrib['reference_name']} - {contrib['outstanding_amount']}")
        
        # Test fetching all items
        from shg.shg.services.payment.bulk_payment_service import get_all_unpaid_items_for_company
        all_items = get_all_unpaid_items_for_company(company)
        print(f"\n📂 Found {len(all_items)} total unpaid items:")
        
        # Group by member to see distribution
        member_distribution = {}
        for item in all_items:
            member_name = item['member_name']
            if member_name not in member_distribution:
                member_distribution[member_name] = 0
            member_distribution[member_name] += 1
        
        print("Distribution by member:")
        for member, count in member_distribution.items():
            print(f"   - {member}: {count} items")
        
        if len(members) > 1 and len(member_distribution) <= 1:
            print("\n⚠️  Potential Issue: Multiple members exist but items are only for one member")
            print("   This could mean either:")
            print("   1. Only one member has unpaid items")
            print("   2. The company filter is not working properly")
        else:
            print(f"\n✅ OK: Items distributed across {len(member_distribution)} members")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing fetch functions: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_fetch_functions()