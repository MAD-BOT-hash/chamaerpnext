import unittest
import frappe
from frappe.utils import today, add_months
from frappe.tests.utils import FrappeTestCase

class TestLoanPortfolioReports(FrappeTestCase):
    def setUp(self):
        # Create a test member
        if not frappe.db.exists("SHG Member", "_Test Member"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member",
                "membership_status": "Active",
                "date_joined": today(),
            })
            member.insert()

        # Create a test loan
        if not frappe.db.exists("SHG Loan", "_Test Loan"):
            loan = frappe.get_doc({
                "doctype": "SHG Loan",
                "member": "_Test Member",
                "loan_amount": 10000,
                "interest_rate": 12,
                "interest_type": "Flat Rate",
                "loan_period_months": 12,
                "repayment_frequency": "Monthly",
                "repayment_start_date": today(),
                "company": frappe.db.get_single_value("SHG Settings", "company") or "_Test Company"
            })
            loan.insert()
            loan.submit()
            self.loan = loan.name
        else:
            self.loan = "_Test Loan"

    def tearDown(self):
        # Clean up test data
        if frappe.db.exists("SHG Loan Repayment", {"loan": self.loan}):
            repayment = frappe.get_doc("SHG Loan Repayment", {"loan": self.loan})
            if repayment.docstatus == 1:
                repayment.cancel()
            repayment.delete()
            
        if frappe.db.exists("SHG Loan", self.loan):
            loan = frappe.get_doc("SHG Loan", self.loan)
            if loan.docstatus == 1:
                loan.cancel()
            loan.delete()
            
        if frappe.db.exists("SHG Member", "_Test Member"):
            member = frappe.get_doc("SHG Member", "_Test Member")
            member.delete()

    def test_loan_portfolio_report(self):
        """Test Loan Portfolio report generation."""
        from shg.shg.report.loan_portfolio.loan_portfolio import execute
        
        # Generate report
        columns, data = execute()
        
        # Check that we have at least one loan in the report
        self.assertGreater(len(data), 0)
        
        # Check that the loan is in the report
        loan_found = False
        for row in data:
            if row.loan_id == self.loan:
                loan_found = True
                # Check that total payable includes both principal and interest
                self.assertGreaterEqual(row.total_payable, row.loan_amount)
                break
                
        self.assertTrue(loan_found, "Test loan not found in portfolio report")

    def test_member_loan_summary_report(self):
        """Test Member Loan Summary report generation."""
        from shg.shg.report.member_loan_summary.member_loan_summary import execute
        
        # Generate report with filter for our test member
        filters = {"member": "_Test Member"}
        columns, data = execute(filters)
        
        # Check that we have at least one loan in the report
        self.assertGreater(len(data), 0)
        
        # Check that the loan is in the report
        loan_found = False
        for row in data:
            if row.loan_id == self.loan:
                loan_found = True
                # Check that total payable includes both principal and interest
                self.assertGreaterEqual(row.total_payable, row.loan_amount)
                # Check that outstanding balance is calculated correctly
                self.assertEqual(row.outstanding_balance, row.total_payable - row.total_paid)
                break
                
        self.assertTrue(loan_found, "Test loan not found in member loan summary report")

    def test_loan_aging_report(self):
        """Test Loan Aging report generation."""
        from shg.shg.report.shg_loan_aging.shg_loan_aging import execute
        
        # Generate report
        columns, data = execute()
        
        # Check that we have data
        self.assertGreater(len(data), 0)
        
        # Check that aging buckets sum up correctly
        for row in data:
            if row.loan == self.loan:
                # Total outstanding should equal sum of all aging buckets
                total_aging = row.current + row.days_0_30 + row.days_31_60 + row.days_61_90 + row.days_90_plus
                self.assertAlmostEqual(row.total_outstanding, total_aging, places=2)
                break

    def test_portfolio_summary_report(self):
        """Test Portfolio Summary report generation."""
        from shg.shg.report.shg_portfolio_summary.shg_portfolio_summary import execute
        
        # Generate report
        columns, data = execute()
        
        # Check that we have data
        self.assertGreater(len(data), 0)
        
        # Check that the current month is in the report
        current_month = frappe.utils.formatdate(today(), "yyyy-MM")
        month_found = False
        for row in data:
            if row.month == current_month:
                month_found = True
                # Check that disbursed amount matches our test loan
                self.assertGreaterEqual(row.disbursed_amount, 10000)
                break
                
        self.assertTrue(month_found, "Current month not found in portfolio summary report")

    def test_loan_disbursement_vs_repayment_report(self):
        """Test Loan Disbursement vs Repayment report generation."""
        from shg.shg.report.loan_disbursement_vs_repayment.loan_disbursement_vs_repayment import execute
        
        # Generate report
        columns, data = execute()
        
        # Check that we have data
        self.assertGreater(len(data), 0)
        
        # Check that the current month is in the report
        current_month = frappe.utils.formatdate(today(), "yyyy-MM")
        month_found = False
        for row in data:
            if row.month == current_month:
                month_found = True
                # Check that disbursed amount matches our test loan
                self.assertGreaterEqual(row.disbursed_amount, 10000)
                break
                
        self.assertTrue(month_found, "Current month not found in disbursement vs repayment report")

if __name__ == '__main__':
    unittest.main()