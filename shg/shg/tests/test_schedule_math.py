import unittest
import frappe
from frappe.utils import today
from shg.shg.utils.schedule_math import calculate_emi, calculate_flat_interest, generate_reducing_balance_schedule, generate_flat_rate_schedule

class TestScheduleMath(unittest.TestCase):
    def test_calculate_emi(self):
        """Test EMI calculation for reducing balance loans."""
        # Test case 1: Normal case
        emi = calculate_emi(10000, 12, 12)  # 10000 loan, 12% annual rate, 12 months
        self.assertAlmostEqual(emi, 888.49, places=2)
        
        # Test case 2: Zero interest rate
        emi = calculate_emi(10000, 0, 12)  # 10000 loan, 0% annual rate, 12 months
        self.assertAlmostEqual(emi, 833.33, places=2)
        
        # Test case 3: Single month
        emi = calculate_emi(10000, 12, 1)  # 10000 loan, 12% annual rate, 1 month
        self.assertAlmostEqual(emi, 10100.00, places=2)

    def test_calculate_flat_interest(self):
        """Test flat interest calculation."""
        # Test case: 10000 loan, 12% annual rate, 12 months
        result = calculate_flat_interest(10000, 12, 12)
        
        self.assertAlmostEqual(result["total_interest"], 1200.00, places=2)
        self.assertAlmostEqual(result["monthly_interest"], 100.00, places=2)
        self.assertAlmostEqual(result["total_amount"], 11200.00, places=2)
        self.assertAlmostEqual(result["monthly_installment"], 933.33, places=2)

    def test_generate_reducing_balance_schedule(self):
        """Test generation of reducing balance schedule."""
        schedule = generate_reducing_balance_schedule(10000, 12, 12, today())
        
        # Check that we have 12 installments
        self.assertEqual(len(schedule), 12)
        
        # Check that the first installment has the correct structure
        first_installment = schedule[0]
        self.assertIn("installment_no", first_installment)
        self.assertIn("due_date", first_installment)
        self.assertIn("principal_component", first_installment)
        self.assertIn("interest_component", first_installment)
        self.assertIn("total_payment", first_installment)
        self.assertIn("loan_balance", first_installment)
        self.assertIn("status", first_installment)
        
        # Check that the last balance is 0
        last_installment = schedule[-1]
        self.assertAlmostEqual(last_installment["loan_balance"], 0.00, places=2)
        
        # Check that principal + interest = total payment for first installment
        self.assertAlmostEqual(
            first_installment["principal_component"] + first_installment["interest_component"],
            first_installment["total_payment"],
            places=2
        )

    def test_generate_flat_rate_schedule(self):
        """Test generation of flat rate schedule."""
        schedule = generate_flat_rate_schedule(10000, 12, 12, today())
        
        # Check that we have 12 installments
        self.assertEqual(len(schedule), 12)
        
        # Check that all installments have the same total payment
        total_payments = [inst["total_payment"] for inst in schedule]
        self.assertAlmostEqual(max(total_payments), min(total_payments), places=2)
        
        # Check that the last balance is 0
        last_installment = schedule[-1]
        self.assertAlmostEqual(last_installment["loan_balance"], 0.00, places=2)

if __name__ == '__main__':
    unittest.main()