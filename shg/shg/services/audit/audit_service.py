"""
Audit Service for SHG Enterprise Architecture
Handles audit logging, compliance tracking, and system monitoring
"""
import frappe
from datetime import datetime
from typing import Dict, Any, Optional
import json
import hashlib


class AuditService:
    """Enterprise-grade audit service for SHG operations"""
    
    def __init__(self):
        self.logger = frappe.logger("shg.audit")
    
    def log_action(self, reference_doctype: str, reference_name: str, 
                   action: str, user: str = None, details: Dict = None) -> str:
        """
        Log an audit action with full context
        
        Args:
            reference_doctype: The doctype being audited
            reference_name: The document name
            action: Action performed (Created, Updated, Deleted, etc.)
            user: User who performed the action
            details: Additional details about the action
            
        Returns:
            Audit log document name
        """
        if not user:
            user = frappe.session.user
            
        # Create audit log entry
        audit_log = frappe.get_doc({
            "doctype": "SHG Audit Trail",
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "action": action,
            "user": user,
            "timestamp": frappe.utils.now_datetime(),
            "details": json.dumps(details) if details else None
        })
        
        audit_log.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Log to system logger
        self.logger.info(f"Audit: {action} {reference_doctype} {reference_name} by {user}")
        
        return audit_log.name
    
    def log_contribution_deletion(self, doc, method):
        """Hook method to log contribution deletion"""
        self.log_action(
            "SHG Contribution",
            doc.name,
            "Deleted",
            details={
                "member": doc.member,
                "contribution_type": doc.contribution_type,
                "expected_amount": doc.expected_amount,
                "paid_amount": doc.paid_amount,
                "deletion_reason": "Document deleted"
            }
        )
    
    def log_payment_allocation(self, contribution_name: str, payment_amount: float,
                              payment_entry: str, user: str = None) -> str:
        """Log payment allocation event"""
        return self.log_action(
            "SHG Contribution",
            contribution_name,
            "Payment Allocated",
            user=user,
            details={
                "payment_amount": payment_amount,
                "payment_entry": payment_entry,
                "allocation_timestamp": frappe.utils.now_datetime().isoformat()
            }
        )
    
    def log_payment_reversal(self, contribution_name: str, reversal_amount: float,
                           reason: str, user: str = None) -> str:
        """Log payment reversal event"""
        return self.log_action(
            "SHG Contribution",
            contribution_name,
            "Payment Reversed",
            user=user,
            details={
                "reversal_amount": reversal_amount,
                "reason": reason,
                "reversal_timestamp": frappe.utils.now_datetime().isoformat()
            }
        )
    
    def log_overpayment_attempt(self, contribution_name: str, attempted_amount: float,
                               expected_amount: float, user: str = None) -> str:
        """Log overpayment prevention event"""
        return self.log_action(
            "SHG Contribution",
            contribution_name,
            "Overpayment Prevented",
            user=user,
            details={
                "attempted_amount": attempted_amount,
                "expected_amount": expected_amount,
                "prevention_timestamp": frappe.utils.now_datetime().isoformat()
            }
        )
    
    def log_concurrent_modification(self, contribution_name: str, error_message: str,
                                   user: str = None) -> str:
        """Log concurrent modification attempt"""
        return self.log_action(
            "SHG Contribution",
            contribution_name,
            "Concurrent Modification Blocked",
            user=user,
            details={
                "error_message": error_message,
                "blocking_timestamp": frappe.utils.now_datetime().isoformat()
            }
        )
    
    def log_duplicate_prevention(self, member: str, contribution_type: str,
                                posting_date: str, user: str = None) -> str:
        """Log duplicate contribution prevention"""
        return self.log_action(
            "SHG Contribution",
            "DUPLICATE_PREVENTION",
            "Duplicate Contribution Blocked",
            user=user,
            details={
                "member": member,
                "contribution_type": contribution_type,
                "posting_date": posting_date,
                "prevention_timestamp": frappe.utils.now_datetime().isoformat()
            }
        )
    
    def generate_audit_report(self, start_date: str = None, end_date: str = None,
                             action_filter: str = None) -> Dict:
        """
        Generate comprehensive audit report
        
        Args:
            start_date: Start date for report period
            end_date: End date for report period
            action_filter: Filter by specific action type
            
        Returns:
            Audit report dictionary
        """
        if not start_date:
            start_date = frappe.utils.add_days(frappe.utils.today(), -30)
        if not end_date:
            end_date = frappe.utils.today()
            
        # Build filters
        filters = [
            ["timestamp", ">=", start_date],
            ["timestamp", "<=", f"{end_date} 23:59:59"]
        ]
        
        if action_filter:
            filters.append(["action", "=", action_filter])
            
        # Get audit logs
        audit_logs = frappe.get_all(
            "SHG Audit Trail",
            filters=filters,
            fields=["*"],
            order_by="timestamp desc"
        )
        
        # Generate summary statistics
        action_counts = {}
        user_counts = {}
        doctype_counts = {}
        
        for log in audit_logs:
            # Count by action type
            action = log.action
            action_counts[action] = action_counts.get(action, 0) + 1
            
            # Count by user
            user = log.user
            user_counts[user] = user_counts.get(user, 0) + 1
            
            # Count by doctype
            doctype = log.reference_doctype
            doctype_counts[doctype] = doctype_counts.get(doctype, 0) + 1
        
        return {
            "report_generated": frappe.utils.now_datetime().isoformat(),
            "period_start": start_date,
            "period_end": end_date,
            "total_events": len(audit_logs),
            "action_breakdown": action_counts,
            "user_activity": user_counts,
            "doctype_activity": doctype_counts,
            "recent_events": audit_logs[:50],  # Last 50 events
            "security_events": [log for log in audit_logs if "Prevented" in log.action or "Blocked" in log.action]
        }
    
    def check_compliance_health(self) -> Dict:
        """
        Check system compliance and health metrics
        
        Returns:
            Compliance health report
        """
        # Check for recent security events
        recent_security_events = frappe.get_all(
            "SHG Audit Trail",
            filters=[
                ["timestamp", ">=", frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=-24)],
                ["action", "in", ["Overpayment Prevented", "Duplicate Contribution Blocked", 
                                "Concurrent Modification Blocked"]]
            ],
            fields=["action", "timestamp"]
        )
        
        # Check audit log completeness
        total_audit_logs = frappe.db.count("SHG Audit Trail")
        recent_audit_logs = len(recent_security_events)
        
        # Check for orphaned records
        orphaned_contributions = frappe.db.sql("""
            SELECT COUNT(*) as count
            FROM `tabSHG Contribution` sc
            LEFT JOIN `tabSHG Member` sm ON sc.member = sm.name
            WHERE sm.name IS NULL
        """, as_dict=True)[0].count
        
        return {
            "compliance_status": "HEALTHY" if len(recent_security_events) == 0 else "WARNING",
            "audit_log_completeness": total_audit_logs > 0,
            "recent_security_events": len(recent_security_events),
            "orphaned_records": orphaned_contributions,
            "system_health": {
                "audit_trail_integrity": total_audit_logs > 100,  # Should have substantial audit history
                "recent_activity": recent_audit_logs > 0,
                "data_consistency": orphaned_contributions == 0
            }
        }
    
    def create_compliance_snapshot(self) -> str:
        """
        Create a compliance snapshot for regulatory purposes
        
        Returns:
            Snapshot reference name
        """
        # Get current system state
        compliance_data = {
            "snapshot_timestamp": frappe.utils.now_datetime().isoformat(),
            "total_members": frappe.db.count("SHG Member"),
            "total_contributions": frappe.db.count("SHG Contribution"),
            "total_payments": frappe.db.count("Payment Entry", 
                                            filters={"party_type": "Customer"}),
            "pending_contributions": frappe.db.count("SHG Contribution",
                                                   filters={"payment_status": "Pending"}),
            "paid_contributions": frappe.db.count("SHG Contribution",
                                                filters={"payment_status": "Paid"}),
            "audit_log_entries": frappe.db.count("SHG Audit Trail"),
            "system_version": frappe.get_attr("frappe.__version__"),
            "app_version": frappe.get_attr("shg.__version__", "1.0.0")
        }
        
        # Create snapshot document
        snapshot = frappe.get_doc({
            "doctype": "SHG Compliance Snapshot",
            "snapshot_data": json.dumps(compliance_data, indent=2),
            "snapshot_timestamp": compliance_data["snapshot_timestamp"],
            "total_records": (compliance_data["total_members"] + 
                            compliance_data["total_contributions"] + 
                            compliance_data["total_payments"])
        })
        
        snapshot.insert(ignore_permissions=True)
        frappe.db.commit()
        
        self.logger.info(f"Compliance snapshot created: {snapshot.name}")
        return snapshot.name


# Global audit service instance
audit_service = AuditService()