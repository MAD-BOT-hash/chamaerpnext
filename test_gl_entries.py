#!/usr/bin/env python
"""
Test script to verify GL entries use Customer party type.
"""
import frappe
import os
import sys

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_gl_entries_use_customer_party():
    """Test that GL entries use Customer party type."""
    print("Starting GL entry party type test...")
    
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
            
        for loan in frappe.get_all("SHG Loan", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Loan", loan.name)
            
        for je in frappe.get_all("Journal Entry", filters={"remark": ["like", "Test Member%"]}):
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
            
            # Check that the party_type is Customer and party is the customer link
            credit_entry = None
            for entry in je.accounts:
                if entry.credit_in_account_currency > 0:
                    credit_entry = entry
                    break
                    
            if credit_entry:
                if credit_entry.party_type != "Customer":
                    print(f"ERROR: Expected party_type 'Customer', got '{credit_entry.party_type}'")
                    return False
                    
                if credit_entry.party != member.customer:
                    print(f"ERROR: Expected party '{member.customer}', got '{credit_entry.party}'")
                    return False
                    
                print("Contribution GL entry correctly uses Customer party type")
            else:
                print("ERROR: Could not find credit entry in journal entry")
                return False
        else:
            print("ERROR: No journal entry created for contribution")
            return False
            
        # Create a loan
        print("Creating loan...")
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": member.name,
            "member_name": member.member_name,
            "loan_amount": 10000,
            "interest_rate": 12,
            "loan_period_months": 12,
            "disbursement_date": "2025-10-01",
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        print(f"Created loan: {loan.name}")
        
        # Check the journal entry
        if loan.disbursement_journal_entry:
            je = frappe.get_doc("Journal Entry", loan.disbursement_journal_entry)
            print(f"Journal Entry created: {je.name}")
            
            # Check that the party_type is Customer and party is the customer link
            debit_entry = None
            for entry in je.accounts:
                if entry.debit_in_account_currency > 0:
                    debit_entry = entry
                    break
                    
            if debit_entry:
                if debit_entry.party_type != "Customer":
                    print(f"ERROR: Expected party_type 'Customer', got '{debit_entry.party_type}'")
                    return False
                    
                if debit_entry.party != member.customer:
                    print(f"ERROR: Expected party '{member.customer}', got '{debit_entry.party}'")
                    return False
                    
                print("Loan GL entry correctly uses Customer party type")
            else:
                print("ERROR: Could not find debit entry in journal entry")
                return False
        else:
            print("ERROR: No journal entry created for loan")
            return False
            
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
    success = test_gl_entries_use_customer_party()
    sys.exit(0 if success else 1)