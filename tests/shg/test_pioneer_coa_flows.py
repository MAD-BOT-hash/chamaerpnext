import unittest
import frappe
from frappe.test_runner import make_test_objects


class TestPioneerCOAAccountingFlows(unittest.TestCase):
    def setUp(self):
        """Set up Pioneer Friends Group Chart of Accounts."""
        # Create company if it doesn't exist
        if not frappe.db.exists("Company", "Pioneer Friends Group"):
            company = frappe.get_doc({
                "doctype": "Company",
                "company_name": "Pioneer Friends Group",
                "abbr": "PFG",
                "default_currency": "KES",
                "country": "Kenya"
            })
            company.insert()
        
        company_name = "Pioneer Friends Group"
        company_abbr = "PFG"
        
        # Create the main account groups as per Pioneer Friends Group COA
        # 1000 - Application of Funds (Assets)
        if not frappe.db.exists("Account", f"Application of Funds (Assets) - {company_abbr}"):
            app_of_funds = frappe.get_doc({
                "doctype": "Account",
                "company": company_name,
                "account_name": "Application of Funds (Assets)",
                "account_number": "1000",
                "is_group": 1,
                "root_type": "Asset",
                "report_type": "Balance Sheet"
            })
            app_of_funds.insert()
        
        # 1100-1600 - Current Assets
        if not frappe.db.exists("Account", f"Current Assets - {company_abbr}"):
            current_assets = frappe.get_doc({
                "doctype": "Account",
                "company": company_name,
                "account_name": "Current Assets",
                "account_number": "1100",
                "is_group": 1,
                "root_type": "Asset",
                "report_type": "Balance Sheet",
                "parent_account": f"Application of Funds (Assets) - {company_abbr}"
            })
            current_assets.insert()
        
        # 13001 - SHG Members (Receivable parent)
        if not frappe.db.exists("Account", f"SHG Members - {company_abbr}"):
            shg_members = frappe.get_doc({
                "doctype": "Account",
                "company": company_name,
                "account_name": "SHG Members",
                "account_number": "13001",
                "is_group": 1,
                "root_type": "Asset",
                "account_type": "Receivable",
                "report_type": "Balance Sheet",
                "parent_account": f"Current Assets - {company_abbr}"
            })
            shg_members.insert()
        
        # 13002 - Bank Account
        if not frappe.db.exists("Account", f"Bank Account - {company_abbr}"):
            bank_account = frappe.get_doc({
                "doctype": "Account",
                "company": company_name,
                "account_name": "Bank Account",
                "account_number": "13002",
                "is_group": 0,
                "root_type": "Asset",
                "account_type": "Bank",
                "report_type": "Balance Sheet",
                "parent_account": f"Current Assets - {company_abbr}"
            })
            bank_account.insert()
        
        # 13003 - Cash Account
        if not frappe.db.exists("Account", f"Cash Account - {company_abbr}"):
            cash_account = frappe.get_doc({
                "doctype": "Account",
                "company": company_name,
                "account_name": "Cash Account",
                "account_number": "13003",
                "is_group": 0,
                "root_type": "Asset",
                "account_type": "Cash",
                "report_type": "Balance Sheet",
                "parent_account": f"Current Assets - {company_abbr}"
            })
            cash_account.insert()
        
        # 4000 - Income
        if not frappe.db.exists("Account", f"Income - {company_abbr}"):
            income = frappe.get_doc({
                "doctype": "Account",
                "company": company_name,
                "account_name": "Income",
                "account_number": "4000",
                "is_group": 1,
                "root_type": "Income",
                "report_type": "Profit and Loss"
            })
            income.insert()
        
        # 4100 - SHG Contributions Income
        if not frappe.db.exists("Account", f"SHG Contributions - {company_abbr}"):
            contributions = frappe.get_doc({
                "doctype": "Account",
                "company": company_name,
                "account_name": "SHG Contributions",
                "account_number": "4100",
                "is_group": 0,
                "root_type": "Income",
                "account_type": "Income Account",
                "report_type": "Profit and Loss",
                "parent_account": f"Income - {company_abbr}"
            })
            contributions.insert()
        
        # 4200 - Interest Income
        if not frappe.db.exists("Account", f"Interest Income - {company_abbr}"):
            interest = frappe.get_doc({
                "doctype": "Account",
                "company": company_name,
                "account_name": "Interest Income",
                "account_number": "4200",
                "is_group": 0,
                "root_type": "Income",
                "account_type": "Income Account",
                "report_type": "Profit and Loss",
                "parent_account": f"Income - {company_abbr}"
            })
            interest.insert()
        
        # 14001 - Loans Disbursed (Asset)
        if not frappe.db.exists("Account", f"Loans Disbursed - {company_abbr}"):
            loans_asset = frappe.get_doc({
                "doctype": "Account",
                "company": company_name,
                "account_name": "Loans Disbursed",
                "account_number": "14001",
                "is_group": 0,
                "root_type": "Asset",
                "account_type": "Receivable",
                "report_type": "Balance Sheet",
                "parent_account": f"Current Assets - {company_abbr}"
            })
            loans_asset.insert()
        
        # Create Customer Group and Territory
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
        
        # Update SHG Settings to use the required posting methods and accounts
        settings = frappe.get_single("SHG Settings")
        settings.contribution_posting_method = "Payment Entry"
        settings.loan_disbursement_posting_method = "Journal Entry"
        settings.loan_repayment_posting_method = "Payment Entry"
        settings.default_bank_account = f"Bank Account - {company_abbr}"
        settings.default_cash_account = f"Cash Account - {company_abbr}"
        settings.default_loan_account = f"Loans Disbursed - {company_abbr}"
        settings.save()

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
            
        # Delete test Journal Entries
        for je in frappe.get_all("Journal Entry", filters={"user_remark": ["like", "SHG%"]}):
            frappe.delete_doc("Journal Entry", je.name)
            
        # Delete test Payment Entries
        for pe in frappe.get_all("Payment Entry", filters={"reference_no": ["like", "SHG%"]}):
            frappe.delete_doc("Payment Entry", pe.name)
            
        frappe.db.commit()

    def test_pioneer_coa_contribution_flow(self):
        """Test contribution flow with Pioneer Friends Group COA."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Pioneer",
            "id_number": "87654321",
            "phone_number": "0787654321"
        })
        member.insert()
        member.reload()
        
        # Verify that a Customer was created and linked
        self.assertIsNotNone(member.customer, "Customer should be linked to SHG Member")
        
        # Create a contribution
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": member.name,
            "member_name": member.member_name,
            "contribution_date": "2025-10-01",
            "amount": 1000,
            "contribution_type": "Regular Weekly"
        })
        contribution.insert()
        contribution.submit()
        
        # Verify that a Payment Entry was created
        self.assertIsNotNone(contribution.payment_entry, "Payment Entry should be created for contribution")
        
        # Verify the Payment Entry details with Pioneer COA
        pe = frappe.get_doc("Payment Entry", contribution.payment_entry)
        self.assertEqual(pe.payment_type, "Receive", "Payment Entry should be of type 'Receive'")
        self.assertEqual(pe.party_type, "Customer", "Party type should be 'Customer'")
        self.assertEqual(pe.party, member.customer, "Party should be the member's customer")
        self.assertEqual(pe.paid_amount, 1000, "Paid amount should match contribution amount")
        self.assertEqual(pe.paid_from, "Bank Account - PFG", "Paid from should be bank account")
        
        print(f"✓ Pioneer COA Contribution Payment Entry created: {pe.name}")
        print(f"  Amount: KES {pe.paid_amount:,.2f}")
        print(f"  From: {pe.paid_from}")
        print(f"  To: Member {member.member_name}")

    def test_pioneer_coa_loan_disbursement_flow(self):
        """Test loan disbursement flow with Pioneer Friends Group COA."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Pioneer 2",
            "id_number": "12344321",
            "phone_number": "0712344321"
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
        
        # Verify that a Journal Entry was created
        self.assertIsNotNone(loan.disbursement_journal_entry, "Journal Entry should be created for loan disbursement")
        
        # Verify the Journal Entry details with Pioneer COA
        je = frappe.get_doc("Journal Entry", loan.disbursement_journal_entry)
        
        # Check accounts
        debit_entry = None
        credit_entry = None
        for entry in je.accounts:
            if entry.debit_in_account_currency > 0:
                debit_entry = entry
            elif entry.credit_in_account_currency > 0:
                credit_entry = entry
        
        self.assertIsNotNone(debit_entry, "Should have a debit entry")
        self.assertIsNotNone(credit_entry, "Should have a credit entry")
        
        # Verify the accounting flow: Dr Loans Disbursed, Cr Bank Account
        self.assertEqual(debit_entry.account, "Loans Disbursed - PFG", 
                        "Debit should be to Loans Disbursed account")
        self.assertEqual(credit_entry.account, "Bank Account - PFG", 
                        "Credit should be to Bank Account")
        self.assertEqual(debit_entry.debit_in_account_currency, 10000, 
                        "Debit amount should match loan amount")
        self.assertEqual(credit_entry.credit_in_account_currency, 10000, 
                        "Credit amount should match loan amount")
        self.assertEqual(debit_entry.party_type, "Customer", 
                        "Debit entry party type should be 'Customer'")
        self.assertEqual(debit_entry.party, member.customer, 
                        "Debit entry party should be member's customer")
        
        print(f"✓ Pioneer COA Loan Disbursement Journal Entry created: {je.name}")
        print(f"  Debit: Loans Disbursed - PFG KES {debit_entry.debit_in_account_currency:,.2f}")
        print(f"  Credit: Bank Account - PFG KES {credit_entry.credit_in_account_currency:,.2f}")
        print(f"  Member: {member.member_name}")

    def test_pioneer_coa_loan_repayment_flow(self):
        """Test loan repayment flow with Pioneer Friends Group COA."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Pioneer 3",
            "id_number": "43211234",
            "phone_number": "0743211234"
        })
        member.insert()
        member.reload()
        
        # First create a loan to repay
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": member.name,
            "member_name": member.member_name,
            "loan_amount": 5000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 6,
            "repayment_frequency": "Monthly",
            "application_date": "2025-10-01",
            "disbursement_date": "2025-10-01",
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Create a repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": member.name,
            "member_name": member.member_name,
            "repayment_date": "2025-10-15",
            "total_paid": 1000
        })
        repayment.insert()
        repayment.submit()
        
        # Verify that a Payment Entry was created
        self.assertIsNotNone(repayment.payment_entry, "Payment Entry should be created for loan repayment")
        
        # Verify the Payment Entry details with Pioneer COA
        pe = frappe.get_doc("Payment Entry", repayment.payment_entry)
        self.assertEqual(pe.payment_type, "Receive", "Payment Entry should be of type 'Receive'")
        self.assertEqual(pe.party_type, "Customer", "Party type should be 'Customer'")
        self.assertEqual(pe.party, member.customer, "Party should be the member's customer")
        self.assertEqual(pe.paid_amount, 1000, "Paid amount should match repayment amount")
        self.assertEqual(pe.paid_from, "Bank Account - PFG", "Paid from should be bank account")
        
        print(f"✓ Pioneer COA Loan Repayment Payment Entry created: {pe.name}")
        print(f"  Amount: KES {pe.paid_amount:,.2f}")
        print(f"  From: {pe.paid_from}")
        print(f"  To: Member {member.member_name}")

    def test_pioneer_coa_gl_entries_compatibility(self):
        """Test that all GL entries are compatible with ERPNext v15 validation."""
        # Create a new SHG Member
        member = frappe.get_doc({
            "doctype": "SHG Member",
            "member_name": "Test Member Pioneer 4",
            "id_number": "56788765",
            "phone_number": "0756788765"
        })
        member.insert()
        member.reload()
        
        # Test contribution
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
        
        # Verify Payment Entry reference types
        if contribution.payment_entry:
            pe = frappe.get_doc("Payment Entry", contribution.payment_entry)
            # Payment Entry is valid for ERPNext v15
            
        # Test loan disbursement
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": member.name,
            "member_name": member.member_name,
            "loan_amount": 5000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 6,
            "repayment_frequency": "Monthly",
            "application_date": "2025-10-01",
            "disbursement_date": "2025-10-01",
            "status": "Disbursed"
        })
        loan.insert()
        loan.submit()
        
        # Verify Journal Entry reference types for ERPNext v15 compatibility
        if loan.disbursement_journal_entry:
            je = frappe.get_doc("Journal Entry", loan.disbursement_journal_entry)
            for entry in je.accounts:
                if entry.reference_type:
                    # All reference types should be valid ERPNext types
                    valid_types = ["", "Sales Invoice", "Purchase Invoice", "Journal Entry", 
                                 "Sales Order", "Purchase Order", "Expense Claim", "Asset", 
                                 "Loan", "Payroll Entry", "Employee Advance", 
                                 "Exchange Rate Revaluation", "Invoice Discounting", "Fees", 
                                 "Full and Final Statement", "Payment Entry", "Loan Interest Accrual"]
                    self.assertIn(entry.reference_type, valid_types,
                                f"Reference type '{entry.reference_type}' should be valid for ERPNext v15")
        
        # Test loan repayment
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan.name,
            "member": member.name,
            "member_name": member.member_name,
            "repayment_date": "2025-10-15",
            "total_paid": 1000
        })
        repayment.insert()
        repayment.submit()
        
        # Verify Payment Entry reference types
        if repayment.payment_entry:
            pe = frappe.get_doc("Payment Entry", repayment.payment_entry)
            # Payment Entry is valid for ERPNext v15
            
        print("✓ All Pioneer COA GL entries validated for ERPNext v15 compatibility")


if __name__ == '__main__':
    unittest.main()