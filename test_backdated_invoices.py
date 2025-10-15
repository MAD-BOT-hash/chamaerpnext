#!/usr/bin/env python3
"""
Test script to validate the backdated invoice functionality
"""

import frappe
import os
import sys

# Add the current directory to the path so we can import the app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_backdated_invoices():
    """Test backdated invoice generation"""
    try:
        # Initialize Frappe
        frappe.init(site="test_site", sites_path=".")
        frappe.connect()
        
        print("Testing backdated invoice functionality...")
        
        # Test 1: Create a contribution invoice with backdated supplier invoice date
        from shg.shg.doctype.shg_contribution_invoice.shg_contribution_invoice import generate_multiple_contribution_invoices
        
        # Create invoices with a backdated supplier invoice date
        result = generate_multiple_contribution_invoices(
            contribution_type="Regular Weekly",
            amount=500,
            invoice_date="2025-01-01",  # Past date
            supplier_invoice_date="2025-01-01"  # Same past date
        )
        
        print(f"Created {len(result['created_invoices'])} invoices with backdated supplier invoice date")
        
        # Verify that the invoices were created with correct dates
        for invoice_data in result['created_invoices']:
            invoice = frappe.get_doc("SHG Contribution Invoice", invoice_data['invoice_name'])
            print(f"Invoice {invoice.name}:")
            print(f"  Invoice Date: {invoice.invoice_date}")
            print(f"  Due Date: {invoice.due_date}")
            print(f"  Supplier Invoice Date: {invoice.supplier_invoice_date}")
            
            # Verify that posting date = due date = supplier invoice date
            if invoice.invoice_date == invoice.due_date == invoice.supplier_invoice_date:
                print("  ✓ Dates are correctly synchronized")
            else:
                print("  ✗ Date synchronization failed")
        
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        frappe.destroy()

if __name__ == "__main__":
    test_backdated_invoices()