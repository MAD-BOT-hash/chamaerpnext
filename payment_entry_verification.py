"""
Script to verify and fix broken payment entry links in SHG modules.
This script can be run in the Frappe console to:
1. Verify if a specific payment entry exists
2. Clean up broken payment entry links
"""

import frappe

def verify_payment_entry(payment_entry_name):
    """Verify if a payment entry exists"""
    if not payment_entry_name:
        print("No payment entry name provided")
        return False
        
    # Check if it exists as SHG Payment Entry
    exists_shg = frappe.db.exists("SHG Payment Entry", payment_entry_name)
    # Check if it exists as regular Payment Entry
    exists_regular = frappe.db.exists("Payment Entry", payment_entry_name)
    
    print(f"Payment Entry {payment_entry_name}:")
    print(f"  - SHG Payment Entry exists: {exists_shg}")
    print(f"  - Regular Payment Entry exists: {exists_regular}")
    print(f"  - Any Payment Entry exists: {exists_shg or exists_regular}")
    
    return exists_shg or exists_regular

def clean_broken_payment_entry_links():
    """Clean up broken payment entry links in all SHG modules"""
    print("🔍 Cleaning up broken payment entry links...")
    
    # Clean up SHG Loan Repayment Schedule
    print("  - Cleaning SHG Loan Repayment Schedule...")
    frappe.db.sql("""
        UPDATE `tabSHG Loan Repayment Schedule`
        SET payment_entry=NULL
        WHERE payment_entry IS NOT NULL
          AND payment_entry NOT IN (
            SELECT name FROM `tabSHG Payment Entry`
            UNION
            SELECT name FROM `tabPayment Entry`
          )
    """)
    
    # Clean up SHG Loan Repayment
    print("  - Cleaning SHG Loan Repayment...")
    frappe.db.sql("""
        UPDATE `tabSHG Loan Repayment`
        SET payment_entry=NULL
        WHERE payment_entry IS NOT NULL
          AND payment_entry NOT IN (
            SELECT name FROM `tabSHG Payment Entry`
            UNION
            SELECT name FROM `tabPayment Entry`
          )
    """)
    
    frappe.db.commit()
    print("✅ Cleanup completed successfully!")

def auto_create_payment_entry_for_repayment(repayment_name):
    """Auto-create a payment entry for a loan repayment if missing"""
    try:
        from shg.shg.utils.payment_entry_tools import auto_create_payment_entry
        
        repayment_doc = frappe.get_doc("SHG Loan Repayment", repayment_name)
        
        # Check if payment entry already exists
        if repayment_doc.payment_entry:
            if verify_payment_entry(repayment_doc.payment_entry):
                print(f"Payment entry {repayment_doc.payment_entry} already exists")
                return repayment_doc.payment_entry
            else:
                print(f"⚠️ Payment entry {repayment_doc.payment_entry} not found, recreating...")
        
        # Create new payment entry
        new_payment_entry = auto_create_payment_entry(repayment_doc)
        print(f"✅ Created new payment entry: {new_payment_entry}")
        return new_payment_entry
        
    except Exception as e:
        print(f"❌ Error creating payment entry for {repayment_name}: {str(e)}")
        return None

# Example usage:
# In Frappe console:
# 1. To verify a payment entry:
#    from payment_entry_verification import verify_payment_entry
#    verify_payment_entry("SHPAY-2025-00058")
#
# 2. To clean up broken links:
#    from payment_entry_verification import clean_broken_payment_entry_links
#    clean_broken_payment_entry_links()
#
# 3. To auto-create payment entry for a repayment:
#    from payment_entry_verification import auto_create_payment_entry_for_repayment
#    auto_create_payment_entry_for_repayment("SHLR-2025-000123")