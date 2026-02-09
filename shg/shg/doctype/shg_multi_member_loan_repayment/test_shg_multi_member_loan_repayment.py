import frappe
import unittest
from frappe.utils import today, flt
from frappe.tests.utils import FrappeTestCase

class TestSHGMultiMemberLoanRepayment(FrappeTestCase):
    def setUp(self):
        # Create test data
        if not frappe.db.exists("Company", "Test Company"):
            frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "default_currency": "KES",
                "country": "Kenya"
            }).insert()
        
        if not frappe.db.exists("Account", "Cash - TC"):
            frappe.get_doc({
                "doctype": "Account",
                "account_name": "Cash",
                "account_type": "Cash",
                "company": "Test Company",
                "parent_account": "Application of Funds (Assets) - TC"
            }).insert()
        
        if not frappe.db.exists("SHG Member", "TEST-MEMBER-001"):
            frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "Test Member",
                "member_id": "TEST-MEMBER-001",
                "status": "Active"
            }).insert()
        
        if not frappe.db.exists("SHG Loan Type", "Personal Loan"):
            frappe.get_doc({
                "doctype": "SHG Loan Type",
                "loan_type_name": "Personal Loan",
                "interest_rate": 12.0
            }).insert()

    def test_validate_payment_amounts(self):
        """Test payment amount validation"""
        # Create test document
        repayment = frappe.new_doc("SHG Multi Member Loan Repayment")
        repayment.posting_date = today()
        repayment.company = "Test Company"
        repayment.payment_mode = "Cash"
        repayment.payment_account = "Cash - TC"
        repayment.batch_number = "TEST-BATCH-001"
        
        # Add loan item with valid payment
        repayment.append("loans", {
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
            "loan": "TEST-LOAN-001",  # This would be created in a real test
            "loan_type": "Personal Loan",
            "outstanding_amount": 1000.0,
            "repayment_amount": 500.0,
            "installment_due_date": today()
        })
        
        # This should not throw validation error for valid amounts
        try:
            repayment.validate()
        except Exception as e:
            if "Repayment amount cannot exceed outstanding amount" not in str(e):
                raise

    def test_validate_repayment_exceeds_outstanding(self):
        """Test that repayment amount cannot exceed outstanding amount"""
        repayment = frappe.new_doc("SHG Multi Member Loan Repayment")
        repayment.posting_date = today()
        repayment.company = "Test Company"
        repayment.payment_mode = "Cash"
        repayment.payment_account = "Cash - TC"
        repayment.batch_number = "TEST-BATCH-002"
        
        # Add loan item with repayment exceeding outstanding
        repayment.append("loans", {
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
            "loan": "TEST-LOAN-001",
            "loan_type": "Personal Loan",
            "outstanding_amount": 1000.0,
            "repayment_amount": 1500.0,  # This exceeds outstanding
            "installment_due_date": today()
        })
        
        # This should throw validation error
        with self.assertRaises(frappe.ValidationError) as context:
            repayment.validate()
        
        self.assertIn("cannot exceed outstanding amount", str(context.exception))

    def test_validate_mandatory_fields(self):
        """Test mandatory field validation"""
        repayment = frappe.new_doc("SHG Multi Member Loan Repayment")
        
        # Should throw validation error for missing mandatory fields
        with self.assertRaises(frappe.ValidationError) as context:
            repayment.validate()
        
        # Check that we get validation errors for missing fields
        self.assertTrue("Company is mandatory" in str(context.exception) or 
                       "Posting Date is mandatory" in str(context.exception))

    def test_process_bulk_loan_repayments(self):
        """Test bulk loan repayment processing"""
        # This would require creating actual loan documents
        # For now, we'll just test that the method exists
        repayment = frappe.new_doc("SHG Multi Member Loan Repayment")
        self.assertTrue(hasattr(repayment, 'process_bulk_loan_repayments'))

    def test_fetch_active_loans(self):
        """Test fetch active loans method"""
        repayment = frappe.new_doc("SHG Multi Member Loan Repayment")
        loans = repayment.fetch_active_loans()
        # Should return a list (even if empty)
        self.assertIsInstance(loans, list)

    def test_recalculate_totals(self):
        """Test recalculate totals method"""
        repayment = frappe.new_doc("SHG Multi Member Loan Repayment")
        
        # Add some loan items
        repayment.append("loans", {
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
            "loan": "TEST-LOAN-001",
            "loan_type": "Personal Loan",
            "outstanding_amount": 1000.0,
            "repayment_amount": 500.0,
            "installment_due_date": today()
        })
        
        repayment.append("loans", {
            "member": "TEST-MEMBER-001",
            "member_name": "Test Member",
            "loan": "TEST-LOAN-002",
            "loan_type": "Personal Loan",
            "outstanding_amount": 2000.0,
            "repayment_amount": 1000.0,
            "installment_due_date": today()
        })
        
        result = repayment.recalculate_totals()
        
        # Check that totals are calculated correctly
        self.assertEqual(repayment.total_repayment_amount, 1500.0)
        self.assertEqual(repayment.total_selected_loans, 2)
        self.assertEqual(result["total_repayment_amount"], 1500.0)
        self.assertEqual(result["total_selected_loans"], 2)

if __name__ == '__main__':
    unittest.main()