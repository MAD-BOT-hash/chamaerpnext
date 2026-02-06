import frappe
import unittest
from frappe.utils import today, add_months
from shg.shg.utils.posting_locks import validate_posting_date, lock_month, unlock_month, is_posting_date_locked

class TestPostingLocks(unittest.TestCase):
    def setUp(self):
        """Set up test data"""
        # Create SHG Settings if not exists
        if not frappe.db.exists("SHG Settings"):
            settings = frappe.get_doc({
                "doctype": "SHG Settings"
            })
            settings.insert(ignore_permissions=True)
        
        # Get current settings
        self.settings = frappe.get_single("SHG Settings")
        self.settings.enable_posting_lock = 1
        self.settings.posting_lock_message = "This period is locked for testing."
        self.settings.save()
        
        # Clear any existing locked months
        self.settings.locked_months = []
        self.settings.save()
        
    def test_lock_month_functionality(self):
        """Test locking and unlocking months"""
        # Lock current month
        current_month = frappe.utils.getdate().strftime("%B")
        current_year = frappe.utils.getdate().year
        
        lock_month(current_month, current_year)
        
        # Verify month is locked
        self.settings.reload()
        locked_months = [f"{lm.month} {lm.year}" for lm in self.settings.locked_months if lm.status == "Locked"]
        self.assertIn(f"{current_month} {current_year}", locked_months)
        
        # Unlock the month
        unlock_month(current_month, current_year)
        
        # Verify month is unlocked
        self.settings.reload()
        locked_months = [f"{lm.month} {lm.year}" for lm in self.settings.locked_months if lm.status == "Locked"]
        self.assertNotIn(f"{current_month} {current_year}", locked_months)
        
    def test_posting_date_validation_locked_until(self):
        """Test validation with global lock date"""
        # Set a future lock date
        future_date = add_months(today(), 1)
        self.settings.posting_locked_until = future_date
        self.settings.save()
        
        # Test that posting today should fail
        with self.assertRaises(frappe.ValidationError) as context:
            validate_posting_date(today())
            
        self.assertIn("locked date", str(context.exception))
        
        # Test that posting after the lock date should work
        past_date = add_months(today(), -1)
        try:
            validate_posting_date(past_date)
        except frappe.ValidationError:
            self.fail("Posting date validation should not fail for past dates when locked until future date")
            
    def test_posting_date_validation_locked_month(self):
        """Test validation with specific locked month"""
        # Lock next month
        next_month_date = add_months(today(), 1)
        next_month = next_month_date.strftime("%B")
        next_year = next_month_date.year
        
        lock_month(next_month, next_year)
        
        # Test that posting in locked month should fail
        with self.assertRaises(frappe.ValidationError) as context:
            validate_posting_date(next_month_date)
            
        self.assertIn("locked for posting", str(context.exception))
        
        # Test that posting in current month should work
        current_date = today()
        try:
            validate_posting_date(current_date)
        except frappe.ValidationError:
            self.fail("Posting date validation should not fail for current month")
            
    def test_is_posting_date_locked(self):
        """Test the is_posting_date_locked utility function"""
        # Lock current month
        current_month = frappe.utils.getdate().strftime("%B")
        current_year = frappe.utils.getdate().year
        lock_month(current_month, current_year)
        
        # Test that current date is locked
        self.assertTrue(is_posting_date_locked(today()))
        
        # Unlock the month
        unlock_month(current_month, current_year)
        
        # Test that current date is not locked
        self.assertFalse(is_posting_date_locked(today()))
        
    def test_posting_lock_disabled(self):
        """Test that validation is skipped when posting lock is disabled"""
        # Disable posting lock
        self.settings.enable_posting_lock = 0
        self.settings.save()
        
        # Lock current month
        current_month = frappe.utils.getdate().strftime("%B")
        current_year = frappe.utils.getdate().year
        lock_month(current_month, current_year)
        
        # Test that posting should still work even with locked month
        try:
            validate_posting_date(today())
        except frappe.ValidationError:
            self.fail("Posting date validation should be skipped when posting lock is disabled")
            
    def tearDown(self):
        """Clean up test data"""
        # Reset settings
        self.settings.enable_posting_lock = 0
        self.settings.posting_locked_until = None
        self.settings.locked_months = []
        self.settings.save()

if __name__ == '__main__':
    unittest.main()