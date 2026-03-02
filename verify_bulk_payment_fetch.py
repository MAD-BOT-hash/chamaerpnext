"""
Quick verification script for SHG Bulk Payment fetch buttons
Run this to verify the new fetch functionality works correctly
"""
import frappe


def verify_fetch_functionality():
    """Verify that the fetch unpaid items functionality works"""
    print("🔍 Verifying SHG Bulk Payment Fetch Functionality...")
    print("=" * 60)
    
    try:
        from shg.shg.services.payment.bulk_payment_service import bulk_payment_service
        
        # Test company (use default or first available)
        company = frappe.defaults.get_global_default("company") or "Test Company"
        print(f"🏢 Testing with company: {company}")
        
        # Test fetching unpaid invoices
        print("\n📋 Testing Unpaid Invoices Fetch:")
        invoices = bulk_payment_service.get_unpaid_invoices_for_company(company)
        print(f"✅ Found {len(invoices)} unpaid invoices")
        if invoices:
            print(f"   Sample: {invoices[0]['member_name']} - {invoices[0]['reference_name']}")
        
        # Test fetching unpaid contributions
        print("\n💰 Testing Unpaid Contributions Fetch:")
        contributions = bulk_payment_service.get_unpaid_contributions_for_company(company)
        print(f"✅ Found {len(contributions)} unpaid contributions")
        if contributions:
            print(f"   Sample: {contributions[0]['member_name']} - {contributions[0]['reference_name']}")
        
        # Test fetching unpaid fines
        print("\n⚖️ Testing Unpaid Fines Fetch:")
        fines = bulk_payment_service.get_unpaid_meeting_fines_for_company(company)
        print(f"✅ Found {len(fines)} unpaid fines")
        if fines:
            print(f"   Sample: {fines[0]['member_name']} - {fines[0]['reference_name']}")
        
        # Test fetching all unpaid items
        print("\n📂 Testing All Unpaid Items Fetch:")
        all_items = bulk_payment_service.get_all_unpaid_items_for_company(company)
        print(f"✅ Found {len(all_items)} total unpaid items")
        if all_items:
            print(f"   Sorted by due date, oldest first:")
            for i, item in enumerate(all_items[:3]):  # Show first 3 items
                print(f"   {i+1}. {item['member_name']} - {item['reference_doctype']} - Due: {item.get('due_date', 'N/A')}")
        
        print("\n" + "=" * 60)
        print("🎉 Fetch Functionality Verification Complete!")
        print("All fetch methods are working correctly.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Verification failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def create_sample_data():
    """Create sample data for testing fetch functionality"""
    print("\n📝 Creating Sample Data for Testing...")
    
    try:
        company = frappe.defaults.get_global_default("company") or "Test Company"
        
        # Create sample member if doesn't exist
        if not frappe.db.exists("SHG Member", "SAMPLE-MEMBER-001"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "Sample Member 1",
                "member_id": "SAMPLE-MEMBER-001",
                "company": company
            })
            member.insert()
            print("✅ Created sample member")
        
        # Create sample contribution invoice
        if not frappe.db.exists("SHG Contribution Invoice", "SAMPLE-INVOICE-001"):
            invoice = frappe.get_doc({
                "doctype": "SHG Contribution Invoice",
                "member": "SAMPLE-MEMBER-001",
                "invoice_date": frappe.utils.today(),
                "due_date": frappe.utils.add_days(frappe.utils.today(), 30),
                "amount": 1000,
                "status": "Unpaid",
                "description": "Sample contribution invoice for testing"
            })
            invoice.insert()
            invoice.submit()
            print("✅ Created sample contribution invoice")
        
        # Create sample contribution
        if not frappe.db.exists("SHG Contribution", "SAMPLE-CONTRIBUTION-001"):
            contribution = frappe.get_doc({
                "doctype": "SHG Contribution",
                "member": "SAMPLE-MEMBER-001",
                "contribution_date": frappe.utils.today(),
                "due_date": frappe.utils.add_days(frappe.utils.today(), 15),
                "expected_amount": 500,
                "paid_amount": 0,
                "payment_status": "Pending",
                "contribution_type": "Monthly"
            })
            contribution.insert()
            contribution.submit()
            print("✅ Created sample contribution")
        
        print("✅ Sample data creation complete")
        return True
        
    except Exception as e:
        print(f"❌ Sample data creation failed: {str(e)}")
        return False


if __name__ == "__main__":
    # Create sample data first
    if create_sample_data():
        # Then verify functionality
        verify_fetch_functionality()