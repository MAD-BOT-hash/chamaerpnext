import frappe
import unittest
from frappe.utils import today

class TestMultiMemberLoan(unittest.TestCase):
    def setUp(self):
        # Create test members
        self.members = []
        for i in range(3):
            if not frappe.db.exists("SHG Member", f"_Test Member {i}"):
                member = frappe.get_doc({
                    "doctype": "SHG Member",
                    "member_name": f"_Test Member {i}",
                    "membership_status": "Active",
                    "date_joined": today(),
                })
                member.insert()
                self.members.append(member.name)
            else:
                self.members.append(f"_Test Member {i}")

        # Create a test group loan
        self.loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "is_group_loan": 1,
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Reducing Balance",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "repayment_start_date": today(),
            "company": frappe.db.get_single_value("SHG Settings", "company") or "_Test Company"
        })
        
        # Add loan members
        for i, member in enumerate(self.members):
            self.loan.append("loan_members", {
                "member": member,
                "member_name": f"_Test Member {i}",
                "allocated_amount": 3333.33
            })
        
        self.loan.insert()

    def tearDown(self):
        # Clean up test data
        if frappe.db.exists("SHG Loan", self.loan.name):
            loan = frappe.get_doc("SHG Loan", self.loan.name)
            if loan.docstatus == 1:
                loan.cancel()
            loan.delete()

        for member_name in self.members:
            if frappe.db.exists("SHG Member", member_name):
                member = frappe.get_doc("SHG Member", member_name)
                member.delete()

    def test_multi_member_loan_validation_passes(self):
        """Test that validation passes when total allocated amount equals loan amount"""
        # Adjust allocations to match exactly
        total_allocated = sum(row.allocated_amount for row in self.loan.loan_members)
        difference = self.loan.loan_amount - total_allocated
        
        # Add the difference to the first member's allocation
        self.loan.loan_members[0].allocated_amount += difference
        self.loan.save()
        
        # Validation should pass without error
        self.assertEqual(self.loan.docstatus, 0)

    def test_multi_member_loan_validation_fails(self):
        """Test that validation fails when total allocated amount doesn't equal loan amount"""
        # Modify one allocation to create a mismatch
        self.loan.loan_members[0].allocated_amount = 3000.00
        self.loan.loan_amount = 10000.00
        
        # Validation should fail
        with self.assertRaises(frappe.ValidationError):
            self.loan.save()

if __name__ == '__main__':
    unittest.main()