#!/usr/bin/env python3
"""
Test script to validate the contribution voucher type functionality
"""

import frappe
import os
import sys

# Add the current directory to the path so we can import the app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_contribution_voucher_type():
    """Test contribution voucher type functionality"""
    try:
        # Initialize Frappe
        frappe.init(site="test_site", sites_path=".")
        frappe.connect()
        
        print("Testing contribution voucher type functionality...")
        
        # Test 1: Create a member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Voucher",
            "id_number": "99887766",
            "phone_number": "0799887766"
        })
        member.insert()
        member.reload()
        print(f"Created member: {member.name}")
        
        # Test 2: Update SHG Settings to use Payment Entry for contributions
        settings = frappe.get_single("SHG Settings")
        settings.contribution_posting_method = "Payment Entry"
        settings.default_contribution_voucher_type = "Contribution Entry"
        settings.save()
        print("Updated SHG Settings to use Payment Entry with Contribution Entry voucher type")
        
        # Test 3: Create a contribution
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": member.name,
            "member_name": member.member_name,
            "contribution_date": "2025-10-15",
            "amount": 1000,
            "contribution_type": "Regular Weekly"
        })
        contribution.insert()
        contribution.submit()
        print(f"Created and submitted contribution: {contribution.name}")
        
        # Test 4: Verify that a Payment Entry was created
        if contribution.payment_entry:
            pe = frappe.get_doc("Payment Entry", contribution.payment_entry)
            print(f"Payment Entry created: {pe.name}")
            print(f"  Voucher Type: {pe.voucher_type}")
            print(f"  Payment Type: {pe.payment_type}")
            print(f"  Party: {pe.party}")
            print(f"  Amount: {pe.paid_amount}")
            
            # Verify voucher type is set correctly
            if pe.voucher_type == "Contribution Entry":
                print("  ✓ Voucher type correctly set to 'Contribution Entry'")
            else:
                print(f"  ✗ Expected voucher type 'Contribution Entry', got '{pe.voucher_type}'")
        else:
            print("  ✗ No Payment Entry created")
        
        # Test 5: Update SHG Settings to use Journal Entry for contributions
        settings.contribution_posting_method = "Journal Entry"
        settings.save()
        print("Updated SHG Settings to use Journal Entry with Contribution Entry voucher type")
        
        # Test 6: Create another contribution
        contribution2 = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": member.name,
            "member_name": member.member_name,
            "contribution_date": "2025-10-16",
            "amount": 500,
            "contribution_type": "Regular Weekly"
        })
        contribution2.insert()
        contribution2.submit()
        print(f"Created and submitted contribution: {contribution2.name}")
        
        # Test 7: Verify that a Journal Entry was created
        if contribution2.journal_entry:
            je = frappe.get_doc("Journal Entry", contribution2.journal_entry)
            print(f"Journal Entry created: {je.name}")
            print(f"  Voucher Type: {je.voucher_type}")
            print(f"  Posting Date: {je.posting_date}")
            
            # Verify voucher type is set correctly
            if je.voucher_type == "Contribution Entry":
                print("  ✓ Voucher type correctly set to 'Contribution Entry'")
            else:
                print(f"  ✗ Expected voucher type 'Contribution Entry', got '{je.voucher_type}'")
        else:
            print("  ✗ No Journal Entry created")
        
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        frappe.destroy()

if __name__ == "__main__":
    test_contribution_voucher_type()