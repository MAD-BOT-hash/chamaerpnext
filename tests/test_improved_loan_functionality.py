import unittest
import frappe
from frappe.utils import nowdate, add_days, add_months

class TestImprovedLoanFunctionality(unittest.TestCase):
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
            
        # Create company if it doesn't exist
        if not frappe.db.exists("Company", "Test Company"):
            company = frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "abbr": "TC",
                "default_currency": "KES"
            })
            company.insert()
            
        # Create accounts
        self.create_test_accounts()
            
        frappe.db.commit()

    def create_test_accounts(self):
        """Create test accounts."""
        company = "Test Company"
        abbr = "TC"
        
        # Create parent accounts if they don't exist
        if not frappe.db.exists("Account", f"Application of Funds (Assets) - {abbr}"):
            parent_asset = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Application of Funds (Assets)",
                "is_group": 1,
                "root_type": "Asset",
                "report_type": "Balance Sheet"
            })
            parent_asset.insert()
            
        if not frappe.db.exists("Account", f"Current Assets - {abbr}"):
            current_assets = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Current Assets",
                "is_group": 1,
                "root_type": "Asset",
                "report_type": "Balance Sheet",
                "parent_account": f"Application of Funds (Assets) - {abbr}"
            })
            current_assets.insert()
            
        if not frappe.db.exists("Account", f"Bank Accounts - {abbr}"):
            bank_parent = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Bank Accounts",
                "is_group": 1,
                "root_type": "Asset",
                "report_type": "Balance Sheet",
                "parent_account": f"Current Assets - {abbr}"
            })
            bank_parent.insert()
            
        if not frappe.db.exists("Account", f"Cash In Hand - {abbr}"):
            cash_parent = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Cash In Hand",
                "is_group": 1,
                "root_type": "Asset",
                "report_type": "Balance Sheet",
                "parent_account": f"Current Assets - {abbr}"
            })
            cash_parent.insert()
            
        if not frappe.db.exists("Account", f"Income - {abbr}"):
            income_parent = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Income",
                "is_group": 1,
                "root_type": "Income",
                "report_type": "Profit and Loss"
            })
            income_parent.insert()
            
        if not frappe.db.exists("Account", f"Direct Income - {abbr}"):
            direct_income = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Direct Income",
                "is_group": 1,
                "root_type": "Income",
                "report_type": "Profit and Loss",
                "parent_account": f"Income - {abbr}"
            })
            direct_income.insert()
            
        if not frappe.db.exists("Account", f"Indirect Income - {abbr}"):
            indirect_income = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Indirect Income",
                "is_group": 1,
                "root_type": "Income",
                "report_type": "Profit and Loss",
                "parent_account": f"Income - {abbr}"
            })
            indirect_income.insert()
            
        # Create specific accounts
        if not frappe.db.exists("Account", f"Test Bank - {abbr}"):
            bank_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Test Bank",
                "account_type": "Bank",
                "is_group": 0,
                "root_type": "Asset",
                "parent_account": f"Bank Accounts - {abbr}"
            })
            bank_account.insert()
            
        if not frappe.db.exists("Account", f"Test Cash - {abbr}"):
            cash_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Test Cash",
                "account_type": "Cash",
                "is_group": 0,
                "root_type": "Asset",
                "parent_account": f"Cash In Hand - {abbr}"
            })
            cash_account.insert()
            
        if not frappe.db.exists("Account", f"Test Loans - {abbr}"):
            loan_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Test Loans",
                "account_type": "Receivable",
                "is_group": 0,
                "root_type": "Asset",
                "parent_account": f"Current Assets - {abbr}"
            })
            loan_account.insert()
            
        if not frappe.db.exists("Account", f"Test Contributions - {abbr}"):
            income_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Test Contributions",
                "account_type": "Income Account",
                "is_group": 0,
                "root_type": "Income",
                "parent_account": f"Direct Income - {abbr}"
            })
            income_account.insert()
            
        if not frappe.db.exists("Account", f"Test Interest Income - {abbr}"):
            interest_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Test Interest Income",
                "account_type": "Income Account",
                "is_group": 0,
                "root_type": "Income",
                "parent_account": f"Indirect Income - {abbr}"
            })
            interest_account.insert()
            
        if not frappe.db.exists("Account", f"Test Penalty Income - {abbr}"):
            penalty_account = frappe.get_doc({
                "doctype": "Account",
                "company": company,
                "account_name": "Test Penalty Income",
                "account_type": "Income Account",
                "is_group": 0,
                "root_type": "Income",
                "parent_account": f"Indirect Income - {abbr}"
            })
            penalty_account.insert()

    def tearDown(self):
        """Clean up test data."""
        # Delete test SHG Members
        for member in frappe.get_all("SHG Member", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Member", member.name)
            
        # Delete test Customers
        for customer in frappe.get_all("Customer", filters={"customer_name": ["like", "Test Member%"]}):
            frappe.delete_doc("Customer", customer.name)
            
        # Delete test Contributions
        for contribution in frappe.get_all("SHG Contribution", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Contribution", contribution.name)
            
        # Delete test Loans
        for loan in frappe.get_all("SHG Loan", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Loan", loan.name)
            
        # Delete test Loan Repayments
        for repayment in frappe.get_all("SHG Loan Repayment", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Loan Repayment", repayment.name)
            
        # Delete test Meeting Fines
        for fine in frappe.get_all("SHG Meeting Fine", filters={"member_name": ["like", "Test Member%"]}):
            frappe.delete_doc("SHG Meeting Fine", fine.name)
            
        # Delete test Payment Entries
        for pe in frappe.get_all("Payment Entry", filters={"reference_no": ["like", "SHG-%"]}):
            frappe.delete_doc("Payment Entry", pe.name)
            
        # Delete test Journal Entries
        for je in frappe.get_all("Journal Entry", filters={"user_remark": ["like", "SHG%"]}):
            frappe.delete_doc("Journal Entry", je.name)
            
        frappe.db.commit()

    def test_loan_reducing_balance_calculation(self):
        """Test that loan repayment calculation works correctly for reducing balance loans."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Loan Calc",
            "id_number": "99887766",
            "phone_number": "0799887766"
        })
        member.insert()
        member.reload()
        
        # Create a reducing balance loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": member.name,
            "member_name": member.member_name,
            "loan_amount": 10000,
            "interest_rate": 12,  # 12% per annum
            "interest_type": "Reducing Balance",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "application_date": "2025-10-01",
            "disbursement_date": "2025-10-01",
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Check that the repayment schedule was generated correctly
        self.assertEqual(len(loan.repayment_schedule), 12, "Should have 12 repayment entries")
        
        # Check first repayment calculation
        first_repayment = loan.repayment_schedule[0]
        # For a 12% annual interest rate on KES 10,000 over 12 months:
        # Monthly rate = 1% (12%/12)
        # Monthly payment = 10000 * 0.01 * (1.01^12) / (1.01^12 - 1) = 888.49
        expected_monthly_payment = 888.49
        self.assertAlmostEqual(first_repayment.total_payment, expected_monthly_payment, places=2,
                             msg="First monthly payment should be approximately KES 888.49")
        
        # Interest for first month = 10000 * 0.01 = 100
        self.assertAlmostEqual(first_repayment.interest_amount, 100, places=2,
                             msg="First month interest should be KES 100")
        
        # Principal for first month = 888.49 - 100 = 788.49
        self.assertAlmostEqual(first_repayment.principal_amount, 788.49, places=2,
                             msg="First month principal should be approximately KES 788.49")
        
        print(f"✓ Reducing balance loan calculation verified")
        print(f"  Monthly Payment: KES {first_repayment.total_payment:,.2f}")
        print(f"  Interest: KES {first_repayment.interest_amount:,.2f}")
        print(f"  Principal: KES {first_repayment.principal_amount:,.2f}")

    def test_loan_repayment_allocation(self):
        """Test that loan repayment allocation works correctly."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Repayment",
            "id_number": "55443322",
            "phone_number": "0755443322"
        })
        member.insert()
        member.reload()
        
        # Create a loan
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": member.name,
            "member_name": member.member_name,
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "application_date": "2025-10-01",
            "disbursement_date": "2025-10-01",
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Create a loan repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": member.name,
            "member_name": member.member_name,
            "repayment_date": add_days(nowdate(), 30),
            "total_paid": 1000
        })
        repayment.insert()
        repayment.submit()
        
        # Check that the repayment breakdown is calculated correctly
        # For flat rate loan: monthly interest = (10000 * 12% / 100) / 12 = 100
        self.assertAlmostEqual(repayment.interest_amount, 100, places=2,
                             msg="Interest amount should be KES 100")
        
        # Principal = 1000 - 100 = 900
        self.assertAlmostEqual(repayment.principal_amount, 900, places=2,
                             msg="Principal amount should be KES 900")
        
        # No penalty since it's on time
        self.assertAlmostEqual(repayment.penalty_amount, 0, places=2,
                             msg="No penalty for on-time payment")
        
        # New balance = 10000 - 900 = 9100
        self.assertAlmostEqual(repayment.balance_after_payment, 9100, places=2,
                             msg="Balance after payment should be KES 9100")
        
        print(f"✓ Loan repayment allocation verified")
        print(f"  Total Paid: KES {repayment.total_paid:,.2f}")
        print(f"  Interest: KES {repayment.interest_amount:,.2f}")
        print(f"  Principal: KES {repayment.principal_amount:,.2f}")
        print(f"  Penalty: KES {repayment.penalty_amount:,.2f}")
        print(f"  New Balance: KES {repayment.balance_after_payment:,.2f}")

    def test_overdue_loan_penalty_calculation(self):
        """Test that overdue loan penalties are calculated correctly."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Penalty",
            "id_number": "11223344",
            "phone_number": "0711223344"
        })
        member.insert()
        member.reload()
        
        # Create a loan with a past due date
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": member.name,
            "member_name": member.member_name,
            "loan_amount": 5000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 6,
            "repayment_frequency": "Monthly",
            "application_date": "2025-01-01",
            "disbursement_date": "2025-01-01",
            "next_due_date": "2025-02-01",  # Past due
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Create a late repayment (30 days overdue)
        late_repayment_date = "2025-03-03"  # 30 days after due date
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": member.name,
            "member_name": member.member_name,
            "repayment_date": late_repayment_date,
            "total_paid": 1000
        })
        repayment.insert()
        
        # Check that penalty is calculated (5% per month on balance)
        # Penalty = 5000 * 0.05 * (30/30) = 250
        self.assertAlmostEqual(repayment.penalty_amount, 250, places=2,
                             msg="Penalty should be KES 250 for 30 days overdue")
        
        print(f"✓ Overdue loan penalty calculation verified")
        print(f"  Penalty Amount: KES {repayment.penalty_amount:,.2f}")

    def test_loan_status_updates(self):
        """Test that loan status updates correctly during repayment."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Status",
            "id_number": "99887766",
            "phone_number": "0799887766"
        })
        member.insert()
        member.reload()
        
        # Create a small loan that can be fully paid
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": member.name,
            "member_name": member.member_name,
            "loan_amount": 1000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 1,
            "repayment_frequency": "Monthly",
            "application_date": "2025-10-01",
            "disbursement_date": "2025-10-01",
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Make a repayment that fully pays off the loan
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": member.name,
            "member_name": member.member_name,
            "repayment_date": add_days(nowdate(), 30),
            "total_paid": 1500  # More than enough to pay off
        })
        repayment.insert()
        repayment.submit()
        
        # Reload loan to check status
        loan.reload()
        
        # Loan should be closed
        self.assertEqual(loan.status, "Closed", "Loan should be closed after full repayment")
        self.assertIsNone(loan.next_due_date, "Next due date should be None for closed loan")
        self.assertAlmostEqual(loan.balance_amount, 0, places=2, 
                             msg="Balance should be zero for closed loan")
        
        print(f"✓ Loan status updates verified")
        print(f"  Status: {loan.status}")
        print(f"  Balance: KES {loan.balance_amount:,.2f}")

if __name__ == '__main__':
    unittest.main()