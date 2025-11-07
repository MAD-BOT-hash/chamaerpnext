"""
Test cases for SHG Loan Services
"""
import unittest
import frappe
from frappe.utils import flt


class TestLoanServices(unittest.TestCase):
    """Test loan service functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        pass
    
    def tearDown(self):
        """Clean up test fixtures."""
        pass
    
    def test_flat_rate_schedule_generation(self):
        """Test flat rate schedule generation."""
        from shg.shg.loan_services.schedule import build_flat_rate_schedule
        
        # Test basic flat rate schedule
        schedule = build_flat_rate_schedule(
            principal=10000,
            interest_rate=12,
            term_months=12
        )
        
        self.assertEqual(len(schedule), 12)
        self.assertEqual(schedule[0]["installment_no"], 1)
        self.assertEqual(schedule[-1]["installment_no"], 12)
        
        # Validate totals
        total_principal = sum(row["principal_due"] for row in schedule)
        total_interest = sum(row["interest_due"] for row in schedule)
        
        self.assertAlmostEqual(total_principal, 10000, places=2)
        self.assertAlmostEqual(total_interest, 1200, places=2)  # 12% of 10000
    
    def test_emi_schedule_generation(self):
        """Test EMI schedule generation."""
        from shg.shg.loan_services.schedule import build_reducing_balance_emi_schedule
        
        # Test basic EMI schedule
        schedule = build_reducing_balance_emi_schedule(
            principal=10000,
            interest_rate=12,
            term_months=12
        )
        
        self.assertEqual(len(schedule), 12)
        self.assertEqual(schedule[0]["installment_no"], 1)
        self.assertEqual(schedule[-1]["installment_no"], 12)
        
        # Validate that EMI is consistent (approximately)
        emis = [row["total_due"] for row in schedule]
        self.assertAlmostEqual(max(emis), min(emis), places=2)
    
    def test_declining_balance_schedule_generation(self):
        """Test declining balance schedule generation."""
        from shg.shg.loan_services.schedule import build_reducing_balance_declining_schedule
        
        # Test declining balance schedule
        schedule = build_reducing_balance_declining_schedule(
            principal=10000,
            interest_rate=12,
            term_months=12
        )
        
        self.assertEqual(len(schedule), 12)
        self.assertEqual(schedule[0]["installment_no"], 1)
        self.assertEqual(schedule[-1]["installment_no"], 12)
        
        # Validate that principal is consistent
        principals = [row["principal_due"] for row in schedule]
        self.assertAlmostEqual(max(principals), min(principals), places=2)
    
    def test_payment_allocation(self):
        """Test payment allocation to schedule."""
        from shg.shg.loan_services.schedule import build_flat_rate_schedule
        from shg.shg.loan_services.allocation import allocate_payment_to_schedule
        
        # Create a simple schedule
        schedule = build_flat_rate_schedule(
            principal=10000,
            interest_rate=12,
            term_months=3
        )
        
        # Allocate partial payment
        updated_schedule, remaining = allocate_payment_to_schedule(schedule, 3000)
        
        self.assertEqual(len(updated_schedule), 3)
        self.assertAlmostEqual(remaining, 0, places=2)
        
        # Check that payment was allocated
        total_paid = sum(row["amount_paid"] for row in updated_schedule)
        self.assertAlmostEqual(total_paid, 3000, places=2)
    
    def test_daily_interest_calculation(self):
        """Test daily interest calculation."""
        from shg.shg.loan_services.accrual import calculate_daily_interest
        
        # Test daily interest calculation
        daily_interest = calculate_daily_interest(
            principal=10000,
            interest_rate=12,
            days=30
        )
        
        # 12% annual rate = 1% monthly = 100 for 30 days on 10000
        self.assertAlmostEqual(daily_interest, 100, places=2)
    
    def test_penalty_calculation(self):
        """Test penalty calculation."""
        from shg.shg.loan_services.accrual import calculate_penalty
        
        # Test penalty calculation
        penalty = calculate_penalty(
            overdue_amount=1000,
            penalty_rate=5,
            days_overdue=30
        )
        
        # 5% annual penalty rate = 500 for 30 days on 1000
        self.assertAlmostEqual(penalty, 4.11, places=2)
    
    def test_writeoff_calculation(self):
        """Test write-off amount calculation."""
        from shg.shg.loan_services.writeoff import calculate_writeoff_amount
        
        # Create a mock loan document
        class MockLoan:
            def __init__(self):
                self.outstanding_principal = 5000
                self.accrued_interest = 200
                self.accrued_penalty = 50
                self.loan_amount = 10000
        
        loan_doc = MockLoan()
        writeoff_amounts = calculate_writeoff_amount(loan_doc)
        
        self.assertEqual(writeoff_amounts["principal"], 5000)
        self.assertEqual(writeoff_amounts["interest"], 200)
        self.assertEqual(writeoff_amounts["penalty"], 50)
        self.assertEqual(writeoff_amounts["total"], 5250)


if __name__ == '__main__':
    unittest.main()