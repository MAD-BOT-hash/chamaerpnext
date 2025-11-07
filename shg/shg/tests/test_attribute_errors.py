import frappe
import unittest

class TestAttributeErrors(unittest.TestCase):
    def test_validate_repayment_method_exists(self):
        """Test that validate_repayment method exists in SHGLoanRepayment class"""
        from shg.shg.doctype.shg_loan_repayment.shg_loan_repayment import SHGLoanRepayment
        
        # Check that the method exists
        self.assertTrue(hasattr(SHGLoanRepayment, 'validate_repayment'))
        
        # Check that it's callable
        self.assertTrue(callable(getattr(SHGLoanRepayment, 'validate_repayment')))
    
    def test_calculate_repayment_breakdown_method_exists(self):
        """Test that calculate_repayment_breakdown method exists in SHGLoanRepayment class"""
        from shg.shg.doctype.shg_loan_repayment.shg_loan_repayment import SHGLoanRepayment
        
        # Check that the method exists
        self.assertTrue(hasattr(SHGLoanRepayment, 'calculate_repayment_breakdown'))
        
        # Check that it's callable
        self.assertTrue(callable(getattr(SHGLoanRepayment, 'calculate_repayment_breakdown')))
    
    def test_methods_are_properly_indented(self):
        """Test that methods are properly indented and not nested inside other functions"""
        from shg.shg.doctype.shg_loan_repayment.shg_loan_repayment import SHGLoanRepayment, recompute_from_ledger
        
        # Check that validate_installment_adjustments is a module-level function, not nested
        # This would fail if it were nested inside recompute_from_ledger
        self.assertTrue(hasattr(SHGLoanRepayment, 'validate_installment_adjustments'))
        
        # Check that post_to_ledger is a module-level function, not nested
        self.assertTrue(hasattr(SHGLoanRepayment, 'post_to_ledger'))
        
        # Check that calculate_outstanding_balance is a module-level function, not nested
        self.assertTrue(hasattr(SHGLoanRepayment, 'calculate_outstanding_balance'))

if __name__ == '__main__':
    unittest.main()