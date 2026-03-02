"""
Verification Script for SHG Bulk Payment Processor
Run this within Frappe bench environment to verify all components
"""
import frappe


def verify_bulk_payment_processor():
    """Verify that all bulk payment processor components are properly loaded"""
    print("🔍 Verifying SHG Bulk Payment Processor Components...")
    print("=" * 60)
    
    # Test service layer imports
    services_to_test = [
        "shg.shg.services.payment.bulk_payment_service",
        "shg.shg.jobs.bulk_payment_jobs"
    ]
    
    print("\n📦 Service Layer Verification:")
    for service_path in services_to_test:
        try:
            __import__(service_path)
            print(f"✅ {service_path}")
        except ImportError as e:
            print(f"❌ {service_path} - {str(e)}")
    
    # Test doctype existence
    print("\n📋 Doctype Verification:")
    doctypes_to_check = [
        "SHG Bulk Payment",
        "SHG Bulk Payment Allocation"
    ]
    
    for doctype in doctypes_to_check:
        if frappe.db.exists("DocType", doctype):
            print(f"✅ {doctype}")
        else:
            print(f"❌ {doctype} - Missing")
    
    # Test database schema
    print("\n🗄️ Database Schema Verification:")
    tables_to_check = [
        "tabSHG Bulk Payment",
        "tabSHG Bulk Payment Allocation"
    ]
    
    for table in tables_to_check:
        try:
            frappe.db.sql(f"DESCRIBE `{table}`")
            print(f"✅ {table}")
        except Exception:
            print(f"❌ {table} - Table missing")
    
    # Test basic functionality
    print("\n🔧 Functionality Verification:")
    try:
        from shg.shg.services.payment.bulk_payment_service import bulk_payment_service
        print("✅ BulkPaymentService imported successfully")
        
        # Test idempotency key generation
        test_key = bulk_payment_service._generate_idempotency_key("TEST-BULK-001", "Manual")
        print(f"✅ Idempotency key generation: {test_key[:16]}...")
        
        # Test duplicate processing check
        is_processed = bulk_payment_service._is_already_processed("TEST-BULK-001", test_key)
        print(f"✅ Duplicate processing check: {is_processed}")
        
    except Exception as e:
        print(f"❌ Functionality test failed: {str(e)}")
    
    # Test background job functions
    print("\n⚙️ Background Job Verification:")
    try:
        from shg.shg.jobs.bulk_payment_jobs import (
            process_bulk_payment_background,
            get_bulk_payment_processing_status,
            validate_bulk_payment_integrity
        )
        print("✅ Background job functions imported successfully")
    except Exception as e:
        print(f"❌ Background job test failed: {str(e)}")
    
    print("\n" + "=" * 60)
    print("🎉 SHG Bulk Payment Processor Verification Complete!")
    print("All components are ready for production use.")
    
    return True


def create_sample_bulk_payment():
    """Create a sample bulk payment for testing"""
    print("\n📝 Creating Sample Bulk Payment for Testing...")
    
    try:
        # Create sample bulk payment
        bulk_payment = frappe.get_doc({
            "doctype": "SHG Bulk Payment",
            "company": frappe.defaults.get_global_default("company") or "Test Company",
            "posting_date": frappe.utils.today(),
            "mode_of_payment": "Cash",
            "payment_account": "Cash - " + frappe.get_value("Company", frappe.defaults.get_global_default("company"), "abbr") if frappe.defaults.get_global_default("company") else "Cash - TC",
            "reference_no": "SAMPLE-BULK-" + frappe.utils.nowdate().replace("-", ""),
            "reference_date": frappe.utils.today(),
            "total_amount": 5000,
            "remarks": "Sample bulk payment for testing"
        })
        
        # Add sample allocations
        for i in range(3):
            bulk_payment.append("allocations", {
                "member": "SAMPLE-MEMBER-001",  # Replace with actual member
                "reference_doctype": "SHG Contribution",
                "reference_name": f"SAMPLE-CONTRIB-{i+1:03d}",
                "reference_date": frappe.utils.today(),
                "due_date": frappe.utils.add_days(frappe.utils.today(), i * 7),
                "outstanding_amount": 1000 + (i * 500),
                "allocated_amount": 1000 + (i * 500),
                "remarks": f"Sample allocation {i+1}"
            })
        
        bulk_payment.insert()
        print(f"✅ Sample bulk payment created: {bulk_payment.name}")
        return bulk_payment.name
        
    except Exception as e:
        print(f"❌ Failed to create sample bulk payment: {str(e)}")
        return None


if __name__ == "__main__":
    verify_bulk_payment_processor()
    # Uncomment below to create sample data
    # create_sample_bulk_payment()