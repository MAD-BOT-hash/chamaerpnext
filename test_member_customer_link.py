#!/usr/bin/env python
"""
Test script to verify SHG Member to Customer linking functionality.
"""
import frappe
import os
import sys

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_customer_linking():
    """Test that a Customer is created and linked when an SHG Member is created."""
    print("Starting SHG Member to Customer linking test...")
    
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
            
        frappe.db.commit()
        
        # Clean up any existing test data
        print("Cleaning up existing test data...")
        for member in frappe.get_all("SHG Member", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Member", member.name)
            
        for customer in frappe.get_all("Customer", filters={"customer_name": ["like", "Test Member%"]}):
            frappe.delete_doc("Customer", customer.name)
            
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
        
        # Verify that a Customer was created and linked
        if not member.customer:
            print("ERROR: Customer was not linked to SHG Member")
            return False
            
        print(f"Customer linked to member: {member.customer}")
        
        # Verify the Customer exists
        try:
            customer = frappe.get_doc("Customer", member.customer)
            print(f"Customer document found: {customer.name}")
            
            # Check customer details
            if customer.customer_name != "Test Member 1":
                print(f"ERROR: Customer name mismatch. Expected 'Test Member 1', got '{customer.customer_name}'")
                return False
                
            if customer.is_shg_member != 1:
                print("ERROR: is_shg_member flag not set correctly")
                return False
                
            if customer.shg_member_id != member.name:
                print(f"ERROR: shg_member_id mismatch. Expected '{member.name}', got '{customer.shg_member_id}'")
                return False
                
            if customer.customer_group != "SHG Members":
                print(f"ERROR: Customer group mismatch. Expected 'SHG Members', got '{customer.customer_group}'")
                return False
                
            if customer.territory != "Kenya":
                print(f"ERROR: Territory mismatch. Expected 'Kenya', got '{customer.territory}'")
                return False
                
            print("All customer details verified successfully!")
            
        except Exception as e:
            print(f"ERROR: Failed to retrieve customer document: {str(e)}")
            return False
            
        # Test no duplicate customer creation
        print("Testing duplicate customer prevention...")
        original_customer = member.customer
        
        # Save the member again (simulating an update)
        member.save()
        
        if member.customer != original_customer:
            print("ERROR: Duplicate customer created on member update")
            return False
            
        # Verify only one customer exists with this name
        customers = frappe.get_all("Customer", filters={"customer_name": "Test Member 1"})
        if len(customers) != 1:
            print(f"ERROR: Expected 1 customer, found {len(customers)}")
            return False
            
        print("Duplicate customer prevention test passed!")
        
        # Clean up test data
        print("Cleaning up test data...")
        frappe.delete_doc("SHG Member", member.name)
        frappe.delete_doc("Customer", customer.name)
        frappe.db.commit()
        
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
    success = test_customer_linking()
    sys.exit(0 if success else 1)