import unittest
import frappe
from frappe.test_runner import make_test_objects


class TestSHGMember(unittest.TestCase):
    def setUp(self):
        """Set up test dependencies."""
        # Create required dependencies
        if not frappe.db.exists("Customer Group", "SHG Members"):
            customer_group = frappe.get_doc({
                "doctype": "Customer Group",
                "customer_group_name": "SHG Members",
                "parent_customer_group": "All Customer Groups",
                "is_group": 0
            })
            customer_group.insert()
            
        if not frappe.db.exists("Territory", "Kenya"):
            territory = frappe.get_doc({
                "doctype": "Territory",
                "territory_name": "Kenya",
                "parent_territory": "All Territories",
                "is_group": 0
            })
            territory.insert()
            
        frappe.db.commit()

    def tearDown(self):
        """Clean up test data."""
        # Delete test SHG Members
        for member in frappe.get_all("SHG Member", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Member", member.name)
            
        # Delete test Customers
        for customer in frappe.get_all("Customer", filters={"customer_name": ["like", "Test Member%"]}):
            frappe.delete_doc("Customer", customer.name)
            
        frappe.db.commit()

    def test_customer_linking_on_member_creation(self):
        """Test that a Customer is created and linked when an SHG Member is created."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member 1",
            "id_number": "12345678",
            "phone_number": "0712345678"
        })
        member.insert()
        
        # Verify that a Customer was created and linked
        self.assertIsNotNone(member.customer, "Customer should be linked to SHG Member")
        
        # Verify the Customer exists
        customer = frappe.get_doc("Customer", member.customer)
        self.assertEqual(customer.customer_name, "Test Member 1")
        self.assertEqual(customer.is_shg_member, 1)
        self.assertEqual(customer.shg_member_id, member.name)
        
        # Verify the Customer has the correct group and territory
        self.assertEqual(customer.customer_group, "SHG Members")
        self.assertEqual(customer.territory, "Kenya")

    def test_no_duplicate_customer_creation(self):
        """Test that no duplicate Customer is created if one already exists."""
        # Create a new SHG Member
        member1 = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member 2",
            "id_number": "87654321",
            "phone_number": "0787654321"
        })
        member1.insert()
        
        # Get the linked customer name
        customer_name = member1.customer
        
        # Create another member with the same name (simulating an update)
        member2 = frappe.get_doc("SHG Member", member1.name)
        member2.save()  # This should not create a new customer
        
        # Verify that the same customer is still linked
        self.assertEqual(member2.customer, customer_name, "No new customer should be created on update")
        
        # Verify only one customer exists with this name
        customers = frappe.get_all("Customer", filters={"customer_name": "Test Member 2"})
        self.assertEqual(len(customers), 1, "Only one customer should exist for this member")


if __name__ == '__main__':
    unittest.main()