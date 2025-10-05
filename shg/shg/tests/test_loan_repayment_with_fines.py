import frappe
import unittest
from frappe.utils import today, add_days

class TestLoanRepaymentWithFines(unittest.TestCase):
    """Test loan repayment with fines functionality"""
    
    def setUp(self):
        """Set up test dependencies"""
        # Create a test company if it doesn't exist
        if not frappe.db.exists("Company", "Test SHG Company"):
            company = frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test SHG Company",
                "abbr": "TSC",
                "default_currency": "KES",
                "country": "Kenya"
            })
            company.insert()
        
        # Create a test member if it doesn't exist
        if not frappe.db.exists("SHG Member", "TEST-MEMBER-003"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "Test Member 3",
                "gender": "Male",
                "date_of_birth": "1985-03-20",
                "phone_number": "+254700000002",
                "email": "test3@example.com",
                "address": "Test Address 3",
                "membership_status": "Active"
            })
            member.insert()
            
        # Create a test customer for the member
        if not frappe.db.exists("Customer", "Test Member 3"):
            customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": "Test Member 3",
                "customer_type": "Individual",
                "customer_group": "All Customer Groups",
                "territory": "All Territories"
            })
            customer.insert()
            
        # Link customer to member
        member = frappe.get_doc("SHG Member", "TEST-MEMBER-003")
        member.customer = "Test Member 3"
        member.save()
        
        # Create test accounts if they don't exist
        company = "Test SHG Company"
        company_abbr = "TSC"
        
        # Create parent accounts first
        if not frappe.db.exists("Account", f"Bank Accounts - {company_abbr}"):
            bank_group = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Bank Accounts",
                "parent_account": f"Current Assets - {company_abbr}",
                "is_group": 1,
                "root_type": "Asset",
                "account_type": "Bank"
            })
            bank_group.insert()
            
        if not frappe.db.exists("Account", f"Test Bank - {company_abbr}"):
            bank_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Test Bank",
                "parent_account": f"Bank Accounts - {company_abbr}",
                "is_group": 0,
                "root_type": "Asset",
                "account_type": "Bank"
            })
            bank_account.insert()
            
        if not frappe.db.exists("Account", f"Cash - {company_abbr}"):
            cash_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Cash",
                "parent_account": f"Current Assets - {company_abbr}",
                "is_group": 0,
                "root_type": "Asset",
                "account_type": "Cash"
            })
            cash_account.insert()
            
        # Update SHG Settings with test accounts
        settings = frappe.get_single("SHG Settings")
        settings.default_bank_account = f"Test Bank - {company_abbr}"
        settings.default_cash_account = f"Cash - {company_abbr}"
        settings.loan_repayment_posting_method = "Payment Entry"
        settings.save()

    def test_loan_repayment_with_penalty_creates_payment_entry(self):
        """Test that loan repayment with penalty creates Payment Entry correctly"""
        # First create a loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "TEST-MEMBER-003",
            "member_name": "Test Member 3",
            "loan_amount": 8000,
            "interest_rate": 10,
            "loan_period_months": 8,
            "disbursement_date": today(),
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Create a repayment with penalty
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": "TEST-MEMBER-003",
            "member_name": "Test Member 3",
            "repayment_date": add_days(today(), 45),  # Late payment to trigger penalty
            "total_paid": 1500,
            "principal_amount": 1000,
            "interest_amount": 300,
            "penalty_amount": 200
        })
        repayment.insert()
        repayment.submit()
        
        # Verify that a Payment Entry was created
        self.assertEqual(repayment.posted_to_gl, 1)
        self.assertIsNotNone(repayment.payment_entry)
        self.assertIsNone(repayment.journal_entry)
        
        # Verify the Payment Entry exists and is submitted
        self.assertTrue(frappe.db.exists("Payment Entry", repayment.payment_entry))
        pe = frappe.get_doc("Payment Entry", repayment.payment_entry)
        self.assertEqual(pe.docstatus, 1)
        
        # Verify Payment Entry details
        self.assertEqual(pe.payment_type, "Receive")
        self.assertEqual(pe.party_type, "SHG Member")
        self.assertEqual(pe.party, "TEST-MEMBER-003")
        self.assertAlmostEqual(pe.paid_amount, 1500, places=2)
        self.assertAlmostEqual(pe.received_amount, 1500, places=2)
        
        # Verify reference fields are set
        self.assertEqual(pe.reference_no, repayment.name)
        self.assertEqual(pe.reference_date, repayment.repayment_date)
        
        # Verify remarks
        self.assertIn("Loan Repayment", pe.remarks)
        self.assertIn(loan.name, pe.remarks)
        self.assertIn("TEST-MEMBER-003", pe.remarks)
        
        # Verify mode of payment and voucher type
        self.assertEqual(pe.mode_of_payment, "Bank")
        self.assertEqual(pe.voucher_type, "Bank Entry")
        
        # Verify custom field for traceability
        self.assertEqual(pe.custom_shg_loan_repayment, repayment.name)
        
        # Verify reference allocation (principal amount)
        self.assertEqual(len(pe.references), 1)
        self.assertEqual(pe.references[0].reference_doctype, "Loan")
        self.assertEqual(pe.references[0].reference_name, loan.name)
        self.assertAlmostEqual(pe.references[0].allocated_amount, 1000, places=2)  # Principal amount
        
        print(f"✓ Loan Repayment with Penalty creates Payment Entry: {pe.name}")
        print(f"  Reference No: {pe.reference_no}")
        print(f"  Reference Date: {pe.reference_date}")
        print(f"  Total Amount: {pe.paid_amount}")
        print(f"  Principal: 1000, Interest: 300, Penalty: 200")

    def test_standalone_meeting_fine_creates_payment_entry(self):
        """Test that standalone meeting fine creates Payment Entry correctly"""
        # Create a standalone meeting fine
        fine = frappe.get_doc({
            "doctype": "SHG Meeting Fine",
            "member": "TEST-MEMBER-003",
            "member_name": "Test Member 3",
            "fine_date": today(),
            "fine_amount": 150,
            "fine_reason": "Absentee",
            "status": "Paid"
        })
        fine.insert()
        fine.submit()
        
        # Verify that a Payment Entry was created
        self.assertEqual(fine.posted_to_gl, 1)
        self.assertIsNotNone(fine.payment_entry)
        self.assertIsNone(fine.journal_entry)
        
        # Verify the Payment Entry exists and is submitted
        self.assertTrue(frappe.db.exists("Payment Entry", fine.payment_entry))
        pe = frappe.get_doc("Payment Entry", fine.payment_entry)
        self.assertEqual(pe.docstatus, 1)
        
        # Verify Payment Entry details
        self.assertEqual(pe.payment_type, "Receive")
        self.assertEqual(pe.party_type, "SHG Member")
        self.assertEqual(pe.party, "TEST-MEMBER-003")
        self.assertAlmostEqual(pe.paid_amount, 150, places=2)
        self.assertAlmostEqual(pe.received_amount, 150, places=2)
        
        # Verify reference fields are set
        self.assertEqual(pe.reference_no, fine.name)
        self.assertEqual(pe.reference_date, fine.fine_date)
        
        # Verify remarks
        self.assertIn("Meeting Fine", pe.remarks)
        self.assertIn("TEST-MEMBER-003", pe.remarks)
        
        # Verify mode of payment and voucher type
        self.assertEqual(pe.mode_of_payment, "Bank")
        self.assertEqual(pe.voucher_type, "Bank Entry")
        
        # Verify custom field for traceability
        self.assertEqual(pe.custom_shg_meeting_fine, fine.name)
        
        print(f"✓ Standalone Meeting Fine creates Payment Entry: {pe.name}")
        print(f"  Reference No: {pe.reference_no}")
        print(f"  Reference Date: {pe.reference_date}")
        print(f"  Amount: {pe.paid_amount}")

# Run tests
if __name__ == "__main__":
    unittest.main()