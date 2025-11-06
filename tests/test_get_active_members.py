import frappe
import unittest
from frappe.utils import today


class TestGetActiveMembers(unittest.TestCase):
    """Test cases for the 'Get Active Members' functionality in SHG Loan."""

    def setUp(self):
        """Set up test data before each test."""
        # Create test members
        self.members = []
        for i in range(3):
            if not frappe.db.exists("SHG Member", f"_Test Member {i+1}"):
                member = frappe.get_doc({
                    "doctype": "SHG Member",
                    "member_name": f"_Test Member {i+1}",
                    "membership_status": "Active",
                    "date_joined": today(),
                })
                member.insert(ignore_permissions=True)
                self.members.append(member.name)
            else:
                self.members.append(f"_Test Member {i+1}")

        # Create one inactive member
        if not frappe.db.exists("SHG Member", "_Test Inactive Member"):
            inactive_member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Inactive Member",
                "membership_status": "Inactive",
                "date_joined": today(),
            })
            inactive_member.insert(ignore_permissions=True)

    def tearDown(self):
        """Clean up test data after each test."""
        # Clean up created loans
        loans = frappe.get_all("SHG Loan", filters={"member": ["in", self.members]})
        for loan in loans:
            frappe.delete_doc("SHG Loan", loan.name)
        
        # Clean up created members
        for member_name in self.members:
            if frappe.db.exists("SHG Member", member_name):
                frappe.delete_doc("SHG Member", member_name)
        
        if frappe.db.exists("SHG Member", "_Test Inactive Member"):
            frappe.delete_doc("SHG Member", "_Test Inactive Member")

    def test_get_active_group_members(self):
        """Test that get_active_group_members returns only active members."""
        # Create a group loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "loan_type": "Group Loan",
            "loan_amount": 15000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "repayment_start_date": today(),
            "company": frappe.db.get_single_value("SHG Settings", "company") or "_Test Company"
        })
        loan.insert(ignore_permissions=True)
        
        # Call the get_active_group_members function
        from shg.shg.doctype.shg_loan.shg_loan import get_active_group_members
        active_members = get_active_group_members(loan.name)
        
        # Check that we get the right number of members (3 active, 1 inactive)
        self.assertEqual(len(active_members), 3)
        
        # Check that all returned members are from our test members list
        returned_member_names = [member["member"] for member in active_members]
        for member_name in self.members:
            self.assertIn(member_name, returned_member_names)
        
        # Check that the inactive member is not included
        for member in active_members:
            self.assertNotEqual(member["member"], "_Test Inactive Member")
        
        # Check that each member has the correct structure
        for member in active_members:
            self.assertIn("member", member)
            self.assertIn("member_name", member)
            self.assertIn("allocated_amount", member)
            self.assertEqual(member["allocated_amount"], 0.0)

    def test_populate_loan_members_table(self):
        """Test that the JavaScript function properly populates the loan members table."""
        # This test would typically be done with Cypress or similar frontend testing tools
        # For now, we'll just verify that the method returns the expected data structure
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "loan_type": "Group Loan",
            "loan_amount": 15000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "repayment_start_date": today(),
            "company": frappe.db.get_single_value("SHG Settings", "company") or "_Test Company"
        })
        loan.insert(ignore_permissions=True)
        
        # Call the get_active_group_members function
        from shg.shg.doctype.shg_loan.shg_loan import get_active_group_members
        active_members = get_active_group_members(loan.name)
        
        # Simulate adding members to the loan_members table
        loan.loan_members = []
        for member_data in active_members:
            row = loan.append("loan_members")
            row.member = member_data["member"]
            row.member_name = member_data["member_name"]
            row.allocated_amount = member_data["allocated_amount"]
        
        # Save the loan
        loan.save(ignore_permissions=True)
        
        # Reload the loan to verify the data was saved
        loan.reload()
        
        # Check that the loan_members table has the correct number of rows
        self.assertEqual(len(loan.loan_members), 3)
        
        # Check that each row has the correct data
        for i, row in enumerate(loan.loan_members):
            self.assertEqual(row.member, active_members[i]["member"])
            self.assertEqual(row.member_name, active_members[i]["member_name"])
            self.assertEqual(row.allocated_amount, active_members[i]["allocated_amount"])