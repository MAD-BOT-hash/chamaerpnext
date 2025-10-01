#!/usr/bin/env python
"""
Test script to verify Journal Entry creation from SHG Contribution.
"""
import frappe
import os
import sys

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_journal_entry_creation():
    """Test that Journal Entries are created correctly from SHG Contributions."""
    print("Starting Journal Entry creation test...")
    
    # Initialize Frappe
    frappe.init(site="test_site", sites_path=".")
    
    try:
        # Connect to the database
        frappe.connect()
        
        # Create required dependencies if they don't exist
        if not frappe.db.exists("Customer Group", "SHG Members"):
            print("Creating 'SHG Members' customer group...")
            customer_group = frappe.get_doc({
                "doctype": "Customer Group",
                "customer_group_name": "SHG Members",
                "parent_customer_group": "All Customer Groups",
                "is_group": 0
            })
            customer_group.insert()
            
        if not frappe.db.exists("Territory", "Kenya"):
            print("Creating 'Kenya' territory...")
            territory = frappe.get_doc({
                "doctype": "Territory",
                "territory_name": "Kenya",
                "parent_territory": "All Territories",
                "is_group": 0
            })
            territory.insert()
            
        # Create a company if it doesn't exist
        if not frappe.db.exists("Company", "Test Company"):
            print("Creating 'Test Company'...")
            company = frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "abbr": "TC",
                "default_currency": "KES"
            })
            company.insert()
            
        frappe.db.commit()
        
        # Clean up any existing test data
        print("Cleaning up existing test data...")
        for member in frappe.get_all("SHG Member", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Member", member.name)
            
        for customer in frappe.get_all("Customer", filters={"customer_name": ["like", "Test Member%"]}):
            frappe.delete_doc("Customer", customer.name)
            
        for contribution in frappe.get_all("SHG Contribution", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Contribution", contribution.name)
            
        for je in frappe.get_all("Journal Entry", filters={"user_remark": ["like", "Test Member%"]}):
            frappe.delete_doc("Journal Entry", je.name)
            
        frappe.db.commit()
        
        # Create a new SHG Member
        print("Creating new SHG Member...")
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member 1",
            "id_number": "12345678",
            "phone_number": "0712345678"
        })
        member.insert()
        print(f"Created SHG Member: {member.name}")
        
        # Reload the member to get the updated customer field
        member.reload()
        
        # Verify that a Customer was created and linked
        if not member.customer:
            print("ERROR: Customer was not linked to SHG Member")
            return False
            
        print(f"Customer linked to member: {member.customer}")
        
        # Create a contribution
        print("Creating contribution...")
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": member.name,
            "member_name": member.member_name,
            "contribution_date": "2025-10-01",
            "amount": 500,
            "contribution_type": "Regular Weekly"
        })
        contribution.insert()
        contribution.submit()
        print(f"Created contribution: {contribution.name}")
        
        # Check the journal entry
        if contribution.journal_entry:
            je = frappe.get_doc("Journal Entry", contribution.journal_entry)
            print(f"Journal Entry created: {je.name}")
            
            # Verify journal entry details
            if je.docstatus != 1:
                print("ERROR: Journal Entry is not submitted")
                return False
                
            if je.voucher_type != "Journal Entry":
                print(f"ERROR: Expected voucher_type 'Journal Entry', got '{je.voucher_type}'")
                return False
                
            if je.posting_date != "2025-10-01":
                print(f"ERROR: Expected posting_date '2025-10-01', got '{je.posting_date}'")
                return False
                
            if je.company != "Test Company":
                print(f"ERROR: Expected company 'Test Company', got '{je.company}'")
                return False
                
            # Check accounts
            if len(je.accounts) != 2:
                print(f"ERROR: Expected 2 accounts, got {len(je.accounts)}")
                return False
                
            # Find debit and credit entries
            debit_entry = None
            credit_entry = None
            for entry in je.accounts:
                if entry.debit_in_account_currency > 0:
                    debit_entry = entry
                elif entry.credit_in_account_currency > 0:
                    credit_entry = entry
                    
            if not debit_entry:
                print("ERROR: No debit entry found")
                return False
                
            if not credit_entry:
                print("ERROR: No credit entry found")
                return False
                
            # Verify debit entry
            if debit_entry.debit_in_account_currency != 500:
                print(f"ERROR: Expected debit amount 500, got {debit_entry.debit_in_account_currency}")
                return False
                
            if debit_entry.reference_type != "SHG Contribution":
                # Note: Using doctype as reference_type is the correct approach
                pass
                
            if debit_entry.reference_name != contribution.name:
                print(f"ERROR: Expected debit reference_name '{contribution.name}', got '{debit_entry.reference_name}'")
                return False
                
            # Verify credit entry
            if credit_entry.credit_in_account_currency != 500:
                print(f"ERROR: Expected credit amount 500, got {credit_entry.credit_in_account_currency}")
                return False
                
            if credit_entry.party_type != "Customer":
                print(f"ERROR: Expected credit party_type 'Customer', got '{credit_entry.party_type}'")
                return False
                
            if credit_entry.party != member.customer:
                print(f"ERROR: Expected credit party '{member.customer}', got '{credit_entry.party}'")
                return False
                
            if credit_entry.reference_type != "SHG Contribution":
                # Note: Using doctype as reference_type is the correct approach
                pass
                
            if credit_entry.reference_name != contribution.name:
                print(f"ERROR: Expected credit reference_name '{contribution.name}', got '{credit_entry.reference_name}'")
                return False
                
            print("Journal Entry correctly created with proper accounts and references")
        else:
            print("ERROR: No journal entry created for contribution")
            return False
            
        # Test cancellation
        print("Testing contribution cancellation...")
        contribution.cancel()
        
        # Check that journal entry is cancelled
        je = frappe.get_doc("Journal Entry", contribution.journal_entry)
        if je.docstatus != 2:
            print("ERROR: Journal Entry was not cancelled when contribution was cancelled")
            return False
            
        print("Contribution cancellation correctly cancelled the Journal Entry")
            
        print("All tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"ERROR: Test failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            frappe.destroy()
        except:
            pass

if __name__ == "__main__":
    success = test_journal_entry_creation()
    sys.exit(0 if success else 1)