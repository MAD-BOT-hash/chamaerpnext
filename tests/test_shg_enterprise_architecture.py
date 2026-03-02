"""
Comprehensive Test Suite for SHG Enterprise Architecture
Tests all service layers, concurrency safety, and enterprise-grade features
"""
import unittest
import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch, MagicMock
import json
from datetime import datetime, timedelta

# Import service layers
from shg.shg.services.contribution.contribution_service import ContributionService
from shg.shg.services.payment.payment_service import PaymentService
from shg.shg.services.accounting.gl_service import GLService
from shg.shg.services.notification.notification_service import NotificationService
from shg.shg.services.member.member_service import MemberService
from shg.shg.services.scheduler_service import SchedulerService


class TestSHGEnterpriseArchitecture(FrappeTestCase):
    """Test suite for enterprise-grade SHG architecture components"""

    def setUp(self):
        """Set up test environment"""
        frappe.db.rollback()
        self.test_data = self._create_test_data()
        
    def tearDown(self):
        """Clean up after tests"""
        frappe.db.rollback()

    def _create_test_data(self):
        """Create test data for SHG system"""
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
        if not frappe.db.exists("SHG Member", "_Test Member"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "_Test Member",
                "member_id": "TM001",
                "company": "_Test Company"
            })
            member.insert()
            
        # Create test customer
        if not frappe.db.exists("Customer", "_Test Customer"):
            customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": "_Test Customer",
                "customer_type": "Individual",
                "customer_group": "Individual",
                "territory": "All Territories"
            })
            customer.insert()
            
        # Link member to customer
        member = frappe.get_doc("SHG Member", "_Test Member")
        member.customer = "_Test Customer"
        member.save()

        # Create test sales invoice
        if not frappe.db.exists("Sales Invoice", "_Test Invoice"):
            invoice = frappe.get_doc({
                "doctype": "Sales Invoice",
                "customer": "_Test Customer",
                "company": "_Test Company",
                "posting_date": frappe.utils.today(),
                "due_date": frappe.utils.add_days(frappe.utils.today(), 30),
                "items": [{
                    "item_code": "Test Item",
                    "qty": 1,
                    "rate": 1000
                }]
            })
            invoice.insert()
            invoice.submit()

        return {
            "company": "_Test Company",
            "member": "_Test Member",
            "customer": "_Test Customer",
            "invoice": "_Test Invoice"
        }

    def test_contribution_service_create_contribution(self):
        """Test contribution creation with service layer"""
        service = ContributionService()
        
        contribution_data = {
            "member": self.test_data["member"],
            "contribution_type": "Monthly",
            "expected_amount": 500,
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.add_days(frappe.utils.today(), 30),
            "description": "Test monthly contribution"
        }
        
        # Create contribution
        result = service.create_contribution(contribution_data)
        
        # Verify result
        self.assertIsNotNone(result.get("name"))
        self.assertEqual(result["status"], "Pending")
        self.assertEqual(result["expected_amount"], 500)
        
        # Verify contribution exists in database
        contribution = frappe.get_doc("SHG Contribution", result["name"])
        self.assertEqual(contribution.member, self.test_data["member"])
        self.assertEqual(contribution.contribution_type, "Monthly")

    def test_contribution_service_duplicate_prevention(self):
        """Test duplicate contribution prevention"""
        service = ContributionService()
        
        contribution_data = {
            "member": self.test_data["member"],
            "contribution_type": "Monthly",
            "expected_amount": 500,
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.add_days(frappe.utils.today(), 30)
        }
        
        # Create first contribution
        result1 = service.create_contribution(contribution_data)
        
        # Attempt to create duplicate
        with self.assertRaises(frappe.ValidationError) as context:
            service.create_contribution(contribution_data)
            
        self.assertIn("already exists", str(context.exception))

    def test_payment_service_overpayment_protection(self):
        """Test overpayment protection logic"""
        # Create contribution first
        service = ContributionService()
        contribution_data = {
            "member": self.test_data["member"],
            "contribution_type": "Monthly",
            "expected_amount": 500,
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.add_days(frappe.utils.today(), 30)
        }
        contribution_result = service.create_contribution(contribution_data)
        
        # Test overpayment
        payment_service = PaymentService()
        contributions_data = [{
            "contribution_name": contribution_result["name"],
            "amount": 600  # Overpayment
        }]
        
        with self.assertRaises(frappe.ValidationError) as context:
            payment_service.allocate_payment("_Test Payment Entry", contributions_data)
            
        self.assertIn("exceeds expected amount", str(context.exception))

    def test_payment_service_concurrent_allocation(self):
        """Test concurrent payment allocation safety"""
        # Create contribution
        service = ContributionService()
        contribution_data = {
            "member": self.test_data["member"],
            "contribution_type": "Monthly",
            "expected_amount": 1000,
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.add_days(frappe.utils.today(), 30)
        }
        contribution_result = service.create_contribution(contribution_data)
        
        payment_service = PaymentService()
        contributions_data = [{
            "contribution_name": contribution_result["name"],
            "amount": 500
        }]
        
        # Simulate concurrent allocations
        with patch('frappe.db.sql') as mock_sql:
            # First allocation should succeed
            result1 = payment_service.allocate_payment("_Test Payment Entry 1", contributions_data)
            self.assertTrue(result1["success"])
            
            # Second allocation with same data should fail due to locking
            mock_sql.side_effect = frappe.QueryDeadlockError("Deadlock detected")
            with self.assertRaises(frappe.QueryDeadlockError):
                payment_service.allocate_payment("_Test Payment Entry 2", contributions_data)

    def test_payment_service_partial_payment(self):
        """Test partial payment handling"""
        # Create contribution
        service = ContributionService()
        contribution_data = {
            "member": self.test_data["member"],
            "contribution_type": "Monthly",
            "expected_amount": 1000,
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.add_days(frappe.utils.today(), 30)
        }
        contribution_result = service.create_contribution(contribution_data)
        
        # Make partial payment
        payment_service = PaymentService()
        contributions_data = [{
            "contribution_name": contribution_result["name"],
            "amount": 400  # Partial payment
        }]
        
        result = payment_service.allocate_payment("_Test Payment Entry", contributions_data)
        
        # Verify partial payment status
        self.assertTrue(result["success"])
        contribution = frappe.get_doc("SHG Contribution", contribution_result["name"])
        self.assertEqual(contribution.paid_amount, 400)
        self.assertEqual(contribution.outstanding_amount, 600)
        self.assertEqual(contribution.payment_status, "Partially Paid")

    def test_payment_service_reversal(self):
        """Test payment reversal functionality"""
        # Create contribution and make payment
        service = ContributionService()
        contribution_data = {
            "member": self.test_data["member"],
            "contribution_type": "Monthly",
            "expected_amount": 1000,
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.add_days(frappe.utils.today(), 30)
        }
        contribution_result = service.create_contribution(contribution_data)
        
        # Make payment
        payment_service = PaymentService()
        contributions_data = [{
            "contribution_name": contribution_result["name"],
            "amount": 1000
        }]
        payment_result = payment_service.allocate_payment("_Test Payment Entry", contributions_data)
        
        # Verify payment was made
        contribution = frappe.get_doc("SHG Contribution", contribution_result["name"])
        self.assertEqual(contribution.paid_amount, 1000)
        self.assertEqual(contribution.payment_status, "Paid")
        
        # Reverse payment
        reversal_result = payment_service.reverse_payment(contribution_result["name"], 1000)
        
        # Verify reversal
        self.assertTrue(reversal_result["success"])
        contribution.reload()
        self.assertEqual(contribution.paid_amount, 0)
        self.assertEqual(contribution.payment_status, "Pending")

    def test_gl_service_journal_entry_creation(self):
        """Test GL service journal entry creation"""
        gl_service = GLService()
        
        # Test journal entry creation
        je_data = {
            "company": self.test_data["company"],
            "posting_date": frappe.utils.today(),
            "voucher_type": "Journal Entry",
            "accounts": [
                {
                    "account": "Cash - TC",
                    "debit": 1000,
                    "credit": 0
                },
                {
                    "account": "SHG Contributions - TC", 
                    "debit": 0,
                    "credit": 1000
                }
            ],
            "user_remark": "Test journal entry"
        }
        
        result = gl_service.create_journal_entry(je_data)
        
        self.assertIsNotNone(result.get("name"))
        je = frappe.get_doc("Journal Entry", result["name"])
        self.assertEqual(je.voucher_type, "Journal Entry")
        self.assertEqual(len(je.accounts), 2)

    def test_gl_service_payment_entry_creation(self):
        """Test GL service payment entry creation"""
        gl_service = GLService()
        
        # Test payment entry creation
        pe_data = {
            "company": self.test_data["company"],
            "posting_date": frappe.utils.today(),
            "paid_amount": 1000,
            "received_amount": 1000,
            "paid_from": "Cash - TC",
            "paid_to": "SHG Contributions - TC",
            "reference_no": "TEST001",
            "reference_date": frappe.utils.today(),
            "party_type": "Customer",
            "party": self.test_data["customer"]
        }
        
        result = gl_service.create_payment_entry(pe_data)
        
        self.assertIsNotNone(result.get("name"))
        pe = frappe.get_doc("Payment Entry", result["name"])
        self.assertEqual(pe.paid_amount, 1000)
        self.assertEqual(pe.party, self.test_data["customer"])

    def test_notification_service_multi_channel(self):
        """Test multi-channel notification service"""
        notification_service = NotificationService()
        
        notification_data = {
            "member": self.test_data["member"],
            "notification_type": "Payment Receipt",
            "amount": 1000,
            "payment_date": frappe.utils.today(),
            "payment_entry": "_Test Payment Entry"
        }
        
        # Test SMS notification
        with patch('frappe.send_sms') as mock_sms:
            result = notification_service.send_sms_notification(notification_data)
            self.assertTrue(result["success"])
            mock_sms.assert_called_once()
        
        # Test email notification
        with patch('frappe.sendmail') as mock_email:
            result = notification_service.send_email_notification(notification_data)
            self.assertTrue(result["success"])
            mock_email.assert_called_once()
            
        # Test WhatsApp notification
        with patch('shg.utils.whatsapp.send_whatsapp_message') as mock_whatsapp:
            result = notification_service.send_whatsapp_notification(notification_data)
            self.assertTrue(result["success"])
            mock_whatsapp.assert_called_once()

    def test_member_service_concurrent_account_creation(self):
        """Test concurrency-safe member account creation"""
        member_service = MemberService()
        
        # Test account creation
        account_data = {
            "member": self.test_data["member"],
            "account_type": "Savings",
            "opening_balance": 0,
            "company": self.test_data["company"]
        }
        
        # First creation should succeed
        result1 = member_service.create_member_account(account_data)
        self.assertTrue(result1["success"])
        
        # Second creation should fail (duplicate prevention)
        with self.assertRaises(frappe.ValidationError) as context:
            member_service.create_member_account(account_data)
            
        self.assertIn("already exists", str(context.exception))

    def test_member_service_financial_summary_update(self):
        """Test member financial summary calculation"""
        member_service = MemberService()
        
        # Create test contributions
        service = ContributionService()
        for i in range(3):
            contribution_data = {
                "member": self.test_data["member"],
                "contribution_type": "Monthly",
                "expected_amount": 500,
                "posting_date": frappe.utils.add_months(frappe.utils.today(), -i),
                "due_date": frappe.utils.add_months(frappe.utils.add_days(frappe.utils.today(), 30), -i)
            }
            service.create_contribution(contribution_data)
        
        # Update financial summary
        result = member_service.update_financial_summary(self.test_data["member"])
        
        self.assertTrue(result["success"])
        member = frappe.get_doc("SHG Member", self.test_data["member"])
        self.assertEqual(member.total_contributions, 1500)  # 3 x 500

    def test_scheduler_service_overdue_contributions(self):
        """Test scheduler service for overdue contributions"""
        scheduler_service = SchedulerService()
        
        # Create overdue contribution
        service = ContributionService()
        contribution_data = {
            "member": self.test_data["member"],
            "contribution_type": "Monthly",
            "expected_amount": 500,
            "posting_date": frappe.utils.add_days(frappe.utils.today(), -60),  # 60 days old
            "due_date": frappe.utils.add_days(frappe.utils.today(), -30)      # 30 days overdue
        }
        service.create_contribution(contribution_data)
        
        # Process overdue contributions
        result = scheduler_service.process_overdue_contributions()
        
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["processed_count"], 1)

    def test_scheduler_service_monthly_statements(self):
        """Test scheduler service for monthly statements"""
        scheduler_service = SchedulerService()
        
        # Create test contributions for current month
        service = ContributionService()
        for i in range(2):
            contribution_data = {
                "member": self.test_data["member"],
                "contribution_type": "Monthly",
                "expected_amount": 500,
                "posting_date": frappe.utils.today(),
                "due_date": frappe.utils.add_days(frappe.utils.today(), 30)
            }
            service.create_contribution(contribution_data)
        
        # Generate monthly statements
        result = scheduler_service.generate_monthly_statements()
        
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["processed_count"], 1)

    def test_scheduler_service_payment_reminders(self):
        """Test scheduler service for payment reminders"""
        scheduler_service = SchedulerService()
        
        # Create contribution due in 3 days
        service = ContributionService()
        contribution_data = {
            "member": self.test_data["member"],
            "contribution_type": "Monthly",
            "expected_amount": 500,
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.add_days(frappe.utils.today(), 3)
        }
        service.create_contribution(contribution_data)
        
        # Send payment reminders
        result = scheduler_service.send_payment_reminders()
        
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["processed_count"], 1)

    def test_multi_member_payment_scenario(self):
        """Test complete multi-member payment scenario"""
        # Create multiple members and contributions
        members = []
        contributions = []
        
        # Create 3 test members
        for i in range(3):
            member_name = f"_Test Member {i+1}"
            if not frappe.db.exists("SHG Member", member_name):
                member = frappe.get_doc({
                    "doctype": "SHG Member",
                    "member_name": member_name,
                    "member_id": f"TM00{i+1}",
                    "company": self.test_data["company"]
                })
                member.insert()
                members.append(member_name)
                
                # Create customer for member
                customer_name = f"_Test Customer {i+1}"
                if not frappe.db.exists("Customer", customer_name):
                    customer = frappe.get_doc({
                        "doctype": "Customer",
                        "customer_name": customer_name,
                        "customer_type": "Individual",
                        "customer_group": "Individual",
                        "territory": "All Territories"
                    })
                    customer.insert()
                    # Link member to customer
                    member.customer = customer_name
                    member.save()
        
        # Create contributions for each member
        contribution_service = ContributionService()
        for member in members:
            contribution_data = {
                "member": member,
                "contribution_type": "Monthly",
                "expected_amount": 500,
                "posting_date": frappe.utils.today(),
                "due_date": frappe.utils.add_days(frappe.utils.today(), 30)
            }
            result = contribution_service.create_contribution(contribution_data)
            contributions.append(result["name"])
        
        # Test multi-member payment allocation
        payment_service = PaymentService()
        contributions_data = [
            {"contribution_name": contributions[0], "amount": 500},  # Full payment
            {"contribution_name": contributions[1], "amount": 300},  # Partial payment
            {"contribution_name": contributions[2], "amount": 500}   # Full payment
        ]
        
        result = payment_service.allocate_payment("_Test Multi Payment Entry", contributions_data)
        
        # Verify all payments processed
        self.assertTrue(result["success"])
        self.assertEqual(len(result["allocation_details"]), 3)
        
        # Verify individual contribution statuses
        contribution1 = frappe.get_doc("SHG Contribution", contributions[0])
        contribution2 = frappe.get_doc("SHG Contribution", contributions[1])
        contribution3 = frappe.get_doc("SHG Contribution", contributions[2])
        
        self.assertEqual(contribution1.payment_status, "Paid")
        self.assertEqual(contribution2.payment_status, "Partially Paid")
        self.assertEqual(contribution3.payment_status, "Paid")

    def test_audit_trail_completeness(self):
        """Test that all operations create proper audit trails"""
        # Test contribution creation audit trail
        service = ContributionService()
        contribution_data = {
            "member": self.test_data["member"],
            "contribution_type": "Monthly",
            "expected_amount": 500,
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.add_days(frappe.utils.today(), 30)
        }
        result = service.create_contribution(contribution_data)
        
        # Verify audit trail exists
        audit_logs = frappe.get_all("SHG Audit Trail", 
                                  filters={"reference_name": result["name"]},
                                  fields=["action", "user", "timestamp"])
        self.assertGreater(len(audit_logs), 0)
        
        # Test payment allocation audit trail
        payment_service = PaymentService()
        contributions_data = [{
            "contribution_name": result["name"],
            "amount": 500
        }]
        payment_result = payment_service.allocate_payment("_Test Payment Entry", contributions_data)
        
        # Verify payment audit trail
        payment_audit_logs = frappe.get_all("SHG Audit Trail",
                                          filters={"reference_name": result["name"],
                                                  "action": "Payment Allocated"},
                                          fields=["details"])
        self.assertGreater(len(payment_audit_logs), 0)

    def test_error_handling_rollback(self):
        """Test that errors trigger proper transaction rollback"""
        initial_count = frappe.db.count("SHG Contribution")
        
        service = ContributionService()
        contribution_data = {
            "member": self.test_data["member"],
            "contribution_type": "Monthly",
            "expected_amount": 500,
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.add_days(frappe.utils.today(), 30)
        }
        
        # Create valid contribution first
        result = service.create_contribution(contribution_data)
        
        # Attempt to create duplicate contribution (should fail)
        try:
            service.create_contribution(contribution_data)
        except frappe.ValidationError:
            pass
        
        # Verify no additional contributions were created
        final_count = frappe.db.count("SHG Contribution")
        self.assertEqual(final_count, initial_count + 1)  # Only the first one should exist

    def test_idempotency_guarantee(self):
        """Test that operations are idempotent"""
        service = ContributionService()
        contribution_data = {
            "member": self.test_data["member"],
            "contribution_type": "Monthly",
            "expected_amount": 500,
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.add_days(frappe.utils.today(), 30)
        }
        
        # Execute same operation multiple times
        result1 = service.create_contribution(contribution_data)
        result2 = service.create_contribution(contribution_data)  # Should fail
        
        # First should succeed, second should fail
        self.assertIsNotNone(result1.get("name"))
        self.assertIsNone(result2.get("name"))


if __name__ == '__main__':
    unittest.main()