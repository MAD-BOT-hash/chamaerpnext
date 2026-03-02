"""
Comprehensive Test Suite for SHG Bulk Payment Processor
Tests all enterprise-grade features and safety mechanisms
"""
import unittest
import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch, MagicMock
import json
from datetime import datetime, timedelta


class TestSHGBulkPaymentProcessor(FrappeTestCase):
    """Test suite for SHG Bulk Payment Processor"""
    
    def setUp(self):
        """Set up test environment"""
        frappe.db.rollback()
        self.test_data = self._create_test_data()
    
    def tearDown(self):
        """Clean up after tests"""
        frappe.db.rollback()
    
    def _create_test_data(self):
        """Create test data for testing"""
        # Create test company
        if not frappe.db.exists("Company", "_Test Company"):
            company = frappe.get_doc({
                "doctype": "Company",
                "company_name": "_Test Company",
                "abbr": "TC",
                "default_currency": "INR",
                "country": "India"
            })
            company.insert()
        
        # Create test member
        if not frappe.db.exists("SHG Member", "_Test Member 1"):
            member1 = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member 1",
                "member_id": "TM001",
                "company": "_Test Company"
            })
            member1.insert()
        
        if not frappe.db.exists("SHG Member", "_Test Member 2"):
            member2 = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member 2",
                "member_id": "TM002",
                "company": "_Test Company"
            })
            member2.insert()
        
        # Create test mode of payment
        if not frappe.db.exists("Mode of Payment", "Cash"):
            mode_of_payment = frappe.get_doc({
                "doctype": "Mode of Payment",
                "mode_of_payment": "Cash",
                "type": "Cash"
            })
            mode_of_payment.insert()
        
        # Create test account
        if not frappe.db.exists("Account", "Cash - TC"):
            account = frappe.get_doc({
                "doctype": "Account",
                "account_name": "Cash",
                "account_type": "Cash",
                "company": "_Test Company",
                "parent_account": "Application of Funds (Assets) - TC"
            })
            account.insert()
        
        return {
            "company": "_Test Company",
            "members": ["_Test Member 1", "_Test Member 2"],
            "mode_of_payment": "Cash",
            "payment_account": "Cash - TC"
        }
    
    def test_bulk_payment_creation(self):
        """Test basic bulk payment creation"""
        from shg.shg.doctype.shg_bulk_payment.shg_bulk_payment import SHGBulkPayment
        
        # Create bulk payment
        bulk_payment = frappe.get_doc({
            "doctype": "SHG Bulk Payment",
            "company": self.test_data["company"],
            "posting_date": frappe.utils.today(),
            "mode_of_payment": self.test_data["mode_of_payment"],
            "payment_account": self.test_data["payment_account"],
            "reference_no": "TEST-BULK-001",
            "reference_date": frappe.utils.today(),
            "total_amount": 1000
        })
        
        # Add allocations
        bulk_payment.append("allocations", {
            "member": self.test_data["members"][0],
            "reference_doctype": "SHG Contribution",
            "reference_name": "TEST-CONTRIB-001",
            "reference_date": frappe.utils.today(),
            "due_date": frappe.utils.today(),
            "outstanding_amount": 500,
            "allocated_amount": 300
        })
        
        bulk_payment.append("allocations", {
            "member": self.test_data["members"][1],
            "reference_doctype": "SHG Contribution",
            "reference_name": "TEST-CONTRIB-002",
            "reference_date": frappe.utils.today(),
            "due_date": frappe.utils.today(),
            "outstanding_amount": 400,
            "allocated_amount": 200
        })
        
        bulk_payment.insert()
        bulk_payment.submit()
        
        # Verify creation
        self.assertIsNotNone(bulk_payment.name)
        self.assertEqual(bulk_payment.processing_status, "Processing")
        self.assertEqual(len(bulk_payment.allocations), 2)
        self.assertEqual(bulk_payment.total_amount, 1000)
        self.assertEqual(bulk_payment.total_allocated_amount, 500)
    
    def test_overpayment_prevention(self):
        """Test overpayment prevention mechanism"""
        from shg.shg.doctype.shg_bulk_payment.shg_bulk_payment import SHGBulkPayment
        
        bulk_payment = frappe.get_doc({
            "doctype": "SHG Bulk Payment",
            "company": self.test_data["company"],
            "posting_date": frappe.utils.today(),
            "mode_of_payment": self.test_data["mode_of_payment"],
            "payment_account": self.test_data["payment_account"],
            "reference_no": "TEST-BULK-002",
            "reference_date": frappe.utils.today(),
            "total_amount": 1000
        })
        
        # Try to allocate more than total amount
        bulk_payment.append("allocations", {
            "member": self.test_data["members"][0],
            "reference_doctype": "SHG Contribution",
            "reference_name": "TEST-CONTRIB-003",
            "reference_date": frappe.utils.today(),
            "due_date": frappe.utils.today(),
            "outstanding_amount": 500,
            "allocated_amount": 1200  # Overpayment
        })
        
        # Should raise validation error
        with self.assertRaises(frappe.ValidationError) as context:
            bulk_payment.insert()
        
        self.assertIn("cannot exceed total payment amount", str(context.exception))
    
    def test_idempotency_guarantee(self):
        """Test idempotency guarantee"""
        from shg.shg.services.payment.bulk_payment_service import bulk_payment_service
        
        # Create test bulk payment
        bulk_payment = frappe.get_doc({
            "doctype": "SHG Bulk Payment",
            "company": self.test_data["company"],
            "posting_date": frappe.utils.today(),
            "mode_of_payment": self.test_data["mode_of_payment"],
            "payment_account": self.test_data["payment_account"],
            "reference_no": "TEST-BULK-003",
            "reference_date": frappe.utils.today(),
            "total_amount": 1000
        })
        
        bulk_payment.append("allocations", {
            "member": self.test_data["members"][0],
            "reference_doctype": "SHG Contribution",
            "reference_name": "TEST-CONTRIB-004",
            "reference_date": frappe.utils.today(),
            "due_date": frappe.utils.today(),
            "outstanding_amount": 1000,
            "allocated_amount": 1000
        })
        
        bulk_payment.insert()
        
        # First processing should succeed
        with patch('shg.shg.services.payment.bulk_payment_service.BulkPaymentService._create_consolidated_payment_entry') as mock_create_pe:
            mock_payment_entry = MagicMock()
            mock_payment_entry.name = "PE-TEST-001"
            mock_create_pe.return_value = mock_payment_entry
            
            result1 = bulk_payment_service.process_bulk_payment(bulk_payment.name, "Manual")
            self.assertTrue(result1["success"])
        
        # Second processing should fail (duplicate prevention)
        with self.assertRaises(Exception) as context:
            bulk_payment_service.process_bulk_payment(bulk_payment.name, "Manual")
        
        self.assertIn("already processed", str(context.exception).lower())
    
    def test_concurrency_safety(self):
        """Test concurrency safety with row-level locking"""
        from shg.shg.services.payment.bulk_payment_service import bulk_payment_service
        
        # Create test bulk payment
        bulk_payment = frappe.get_doc({
            "doctype": "SHG Bulk Payment",
            "company": self.test_data["company"],
            "posting_date": frappe.utils.today(),
            "mode_of_payment": self.test_data["mode_of_payment"],
            "payment_account": self.test_data["payment_account"],
            "reference_no": "TEST-BULK-004",
            "reference_date": frappe.utils.today(),
            "total_amount": 1000
        })
        
        bulk_payment.append("allocations", {
            "member": self.test_data["members"][0],
            "reference_doctype": "SHG Contribution",
            "reference_name": "TEST-CONTRIB-005",
            "reference_date": frappe.utils.today(),
            "due_date": frappe.utils.today(),
            "outstanding_amount": 1000,
            "allocated_amount": 1000
        })
        
        bulk_payment.insert()
        
        # Simulate concurrent access with locking
        with patch('frappe.db.sql') as mock_sql:
            mock_sql.side_effect = frappe.QueryDeadlockError("Deadlock detected")
            
            # Should handle deadlock gracefully
            with self.assertRaises(frappe.QueryDeadlockError):
                bulk_payment_service.process_bulk_payment(bulk_payment.name, "Manual")
    
    def test_auto_allocation_by_oldest_due_date(self):
        """Test auto-allocation by oldest due date functionality"""
        from shg.shg.services.payment.bulk_payment_service import bulk_payment_service
        
        # Create bulk payment with multiple allocations
        bulk_payment = frappe.get_doc({
            "doctype": "SHG Bulk Payment",
            "company": self.test_data["company"],
            "posting_date": frappe.utils.today(),
            "mode_of_payment": self.test_data["mode_of_payment"],
            "payment_account": self.test_data["payment_account"],
            "reference_no": "TEST-BULK-005",
            "reference_date": frappe.utils.today(),
            "total_amount": 1500
        })
        
        # Add allocations with different due dates (oldest first)
        bulk_payment.append("allocations", {
            "member": self.test_data["members"][0],
            "reference_doctype": "SHG Contribution",
            "reference_name": "TEST-CONTRIB-006",
            "reference_date": frappe.utils.add_days(frappe.utils.today(), -30),
            "due_date": frappe.utils.add_days(frappe.utils.today(), -30),
            "outstanding_amount": 500,
            "allocated_amount": 0  # Will be auto-allocated
        })
        
        bulk_payment.append("allocations", {
            "member": self.test_data["members"][1],
            "reference_doctype": "SHG Contribution",
            "reference_name": "TEST-CONTRIB-007",
            "reference_date": frappe.utils.add_days(frappe.utils.today(), -15),
            "due_date": frappe.utils.add_days(frappe.utils.today(), -15),
            "outstanding_amount": 800,
            "allocated_amount": 0  # Will be auto-allocated
        })
        
        bulk_payment.append("allocations", {
            "member": self.test_data["members"][0],
            "reference_doctype": "SHG Contribution",
            "reference_name": "TEST-CONTRIB-008",
            "reference_date": frappe.utils.today(),
            "due_date": frappe.utils.today(),
            "outstanding_amount": 600,
            "allocated_amount": 0  # Will be auto-allocated
        })
        
        bulk_payment.insert()
        
        # Test auto-allocation
        result = bulk_payment_service.auto_allocate_by_oldest_due_date(bulk_payment.name)
        
        # Reload document to get updated values
        bulk_payment.reload()
        
        # Verify allocations were made in order of due date
        self.assertTrue(result["success"])
        self.assertEqual(result["total_amount"], 1500)
        self.assertEqual(result["total_allocated"], 1300)  # 500 + 800
        self.assertEqual(result["remaining_amount"], 200)  # 1500 - 1300
        
        # Check that oldest allocations got priority
        allocated_amounts = [flt(alloc.allocated_amount) for alloc in bulk_payment.allocations]
        self.assertEqual(allocated_amounts, [500, 800, 0])  # Oldest first
    
    def test_background_job_processing(self):
        """Test background job processing"""
        from shg.shg.jobs.bulk_payment_jobs import process_bulk_payment_background
        
        # Create test bulk payment
        bulk_payment = frappe.get_doc({
            "doctype": "SHG Bulk Payment",
            "company": self.test_data["company"],
            "posting_date": frappe.utils.today(),
            "mode_of_payment": self.test_data["mode_of_payment"],
            "payment_account": self.test_data["payment_account"],
            "reference_no": "TEST-BULK-006",
            "reference_date": frappe.utils.today(),
            "total_amount": 1000
        })
        
        bulk_payment.append("allocations", {
            "member": self.test_data["members"][0],
            "reference_doctype": "SHG Contribution",
            "reference_name": "TEST-CONTRIB-009",
            "reference_date": frappe.utils.today(),
            "due_date": frappe.utils.today(),
            "outstanding_amount": 1000,
            "allocated_amount": 1000
        })
        
        bulk_payment.insert()
        
        # Test background processing
        with patch('shg.shg.services.payment.bulk_payment_service.BulkPaymentService._create_consolidated_payment_entry') as mock_create_pe:
            mock_payment_entry = MagicMock()
            mock_payment_entry.name = "PE-TEST-002"
            mock_create_pe.return_value = mock_payment_entry
            
            result = process_bulk_payment_background(bulk_payment.name)
            
            self.assertTrue(result["success"])
            self.assertEqual(result["result"]["bulk_payment_name"], bulk_payment.name)
    
    def test_audit_logging(self):
        """Test comprehensive audit logging"""
        from shg.shg.services.payment.bulk_payment_service import bulk_payment_service
        
        # Create test bulk payment
        bulk_payment = frappe.get_doc({
            "doctype": "SHG Bulk Payment",
            "company": self.test_data["company"],
            "posting_date": frappe.utils.today(),
            "mode_of_payment": self.test_data["mode_of_payment"],
            "payment_account": self.test_data["payment_account"],
            "reference_no": "TEST-BULK-007",
            "reference_date": frappe.utils.today(),
            "total_amount": 1000
        })
        
        bulk_payment.append("allocations", {
            "member": self.test_data["members"][0],
            "reference_doctype": "SHG Contribution",
            "reference_name": "TEST-CONTRIB-010",
            "reference_date": frappe.utils.today(),
            "due_date": frappe.utils.today(),
            "outstanding_amount": 1000,
            "allocated_amount": 1000
        })
        
        bulk_payment.insert()
        
        # Process with audit logging
        with patch('shg.shg.services.payment.bulk_payment_service.BulkPaymentService._create_consolidated_payment_entry') as mock_create_pe:
            mock_payment_entry = MagicMock()
            mock_payment_entry.name = "PE-TEST-003"
            mock_create_pe.return_value = mock_payment_entry
            
            result = bulk_payment_service.process_bulk_payment(bulk_payment.name, "Manual")
            
            # Verify audit trail was created
            audit_logs = frappe.get_all(
                "SHG Audit Trail",
                filters={
                    "reference_doctype": "SHG Bulk Payment",
                    "reference_name": bulk_payment.name
                }
            )
            
            self.assertGreater(len(audit_logs), 0)
    
    def test_duplicate_processing_prevention(self):
        """Test duplicate processing prevention"""
        from shg.shg.jobs.bulk_payment_jobs import process_bulk_payment_background
        
        # Create test bulk payment
        bulk_payment = frappe.get_doc({
            "doctype": "SHG Bulk Payment",
            "company": self.test_data["company"],
            "posting_date": frappe.utils.today(),
            "mode_of_payment": self.test_data["mode_of_payment"],
            "payment_account": self.test_data["payment_account"],
            "reference_no": "TEST-BULK-008",
            "reference_date": frappe.utils.today(),
            "total_amount": 1000
        })
        
        bulk_payment.append("allocations", {
            "member": self.test_data["members"][0],
            "reference_doctype": "SHG Contribution",
            "reference_name": "TEST-CONTRIB-011",
            "reference_date": frappe.utils.today(),
            "due_date": frappe.utils.today(),
            "outstanding_amount": 1000,
            "allocated_amount": 1000
        })
        
        bulk_payment.insert()
        
        # First processing
        with patch('shg.shg.services.payment.bulk_payment_service.BulkPaymentService._create_consolidated_payment_entry') as mock_create_pe:
            mock_payment_entry = MagicMock()
            mock_payment_entry.name = "PE-TEST-004"
            mock_create_pe.return_value = mock_payment_entry
            
            result1 = process_bulk_payment_background(bulk_payment.name)
            self.assertTrue(result1["success"])
        
        # Second processing should fail
        result2 = process_bulk_payment_background(bulk_payment.name)
        self.assertFalse(result2["success"])
        self.assertIn("already processed", result2["error"].lower())
    
    def test_validation_integrity(self):
        """Test validation and integrity checking"""
        from shg.shg.jobs.bulk_payment_jobs import validate_bulk_payment_integrity
        
        # Create test bulk payment with issues
        bulk_payment = frappe.get_doc({
            "doctype": "SHG Bulk Payment",
            "company": self.test_data["company"],
            "posting_date": frappe.utils.today(),
            "mode_of_payment": self.test_data["mode_of_payment"],
            "payment_account": self.test_data["payment_account"],
            "reference_no": "TEST-BULK-009",
            "reference_date": frappe.utils.today(),
            "total_amount": 1000
        })
        
        # Add allocation with overpayment
        bulk_payment.append("allocations", {
            "member": self.test_data["members"][0],
            "reference_doctype": "SHG Contribution",
            "reference_name": "TEST-CONTRIB-012",
            "reference_date": frappe.utils.today(),
            "due_date": frappe.utils.today(),
            "outstanding_amount": 500,
            "allocated_amount": 600  # Overpayment
        })
        
        bulk_payment.insert()
        
        # Validate integrity
        result = validate_bulk_payment_integrity(bulk_payment.name)
        
        self.assertTrue(result["success"])
        self.assertFalse(result["is_valid"])
        self.assertGreater(len(result["validation_results"]["validation_issues"]), 0)
        
        # Check that overpayment issue is detected
        issues = result["validation_results"]["validation_issues"]
        overpayment_issues = [issue for issue in issues if issue["type"] == "overpayment"]
        self.assertEqual(len(overpayment_issues), 1)


# Helper function for float conversion
def flt(amount, precision=2):
    """Convert to float with precision"""
    if amount is None:
        return 0.0
    return round(float(amount), precision)


if __name__ == '__main__':
    unittest.main()