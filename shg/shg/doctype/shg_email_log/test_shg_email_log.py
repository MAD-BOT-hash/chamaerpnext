# Copyright (c) 2026, SHG Solutions
# License: MIT

import frappe
import unittest
from frappe.tests.utils import FrappeTestCase

class TestSHGEmailLog(FrappeTestCase):
    def setUp(self):
        # Create test member if it doesn't exist
        if not frappe.db.exists("SHG Member", "TEST-MEMBER-001"):
            frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "Test Member",
                "member_id": "TEST-MEMBER-001",
                "email": "test@example.com",
                "status": "Active"
            }).insert()

    def test_create_email_log(self):
        """Test creating email log entry"""
        email_log = frappe.new_doc("SHG Email Log")
        email_log.member = "TEST-MEMBER-001"
        email_log.email_address = "test@example.com"
        email_log.subject = "Test Statement Email"
        email_log.status = "Sent"
        email_log.document_type = "Member Statement"
        
        email_log.insert()
        self.assertTrue(frappe.db.exists("SHG Email Log", email_log.name))
        
        # Verify auto-populated fields
        self.assertEqual(email_log.sent_by, frappe.session.user)

    def test_email_log_validation(self):
        """Test email log validation"""
        email_log = frappe.new_doc("SHG Email Log")
        
        # Should fail without required fields
        with self.assertRaises(frappe.ValidationError):
            email_log.insert()
        
        # Add required fields
        email_log.member = "TEST-MEMBER-001"
        email_log.email_address = "test@example.com"
        email_log.subject = "Test Email"
        email_log.status = "Sent"
        email_log.document_type = "Member Statement"
        
        # Should succeed now
        email_log.insert()
        self.assertTrue(frappe.db.exists("SHG Email Log", email_log.name))

    def test_email_log_status_update(self):
        """Test updating email log status"""
        # Create initial log
        email_log = frappe.new_doc("SHG Email Log")
        email_log.member = "TEST-MEMBER-001"
        email_log.email_address = "test@example.com"
        email_log.subject = "Test Email"
        email_log.status = "Pending"
        email_log.document_type = "Member Statement"
        email_log.insert()
        
        # Update status
        email_log.status = "Sent"
        email_log.save()
        
        # Verify update
        updated_log = frappe.get_doc("SHG Email Log", email_log.name)
        self.assertEqual(updated_log.status, "Sent")

if __name__ == '__main__':
    unittest.main()