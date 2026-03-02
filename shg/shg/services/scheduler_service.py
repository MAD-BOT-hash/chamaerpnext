"""
Scheduler Service Layer
Enterprise-grade background job processing with proper error handling and monitoring
"""
import frappe
from frappe import _
from frappe.utils import now, add_days, getdate
from typing import Dict, List, Optional
import json
from datetime import datetime, timedelta
import logging

class SchedulerServiceError(Exception):
    """Base exception for scheduler service errors"""
    pass

class SchedulerService:
    """
    Enterprise-grade scheduler service with:
    - Proper background job management
    - Error handling and retry mechanisms
    - Monitoring and alerting
    - Audit trail
    """
    
    def __init__(self):
        self.logger = frappe.logger("scheduler_service", allow_site=True)
    
    def process_overdue_contributions(self) -> Dict:
        """
        Process overdue contributions and update statuses
        
        Returns:
            Dict with processing results
        """
        try:
            # Get overdue contributions
            overdue_contributions = self._get_overdue_contributions()
            
            if not overdue_contributions:
                return {
                    'status': 'success',
                    'processed_count': 0,
                    'message': 'No overdue contributions found',
                    'timestamp': now()
                }
            
            # Process each overdue contribution
            processed_count = 0
            failed_count = 0
            results = []
            
            for contribution in overdue_contributions:
                try:
                    result = self._process_overdue_contribution(contribution)
                    results.append(result)
                    processed_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to process overdue contribution {contribution.name}: {str(e)}")
                    failed_count += 1
                    results.append({
                        'contribution': contribution.name,
                        'status': 'failed',
                        'error': str(e)
                    })
            
            # Log completion
            self._log_scheduler_job(
                'overdue_contributions',
                processed_count,
                failed_count,
                results
            )
            
            return {
                'status': 'completed',
                'total_found': len(overdue_contributions),
                'processed_count': processed_count,
                'failed_count': failed_count,
                'results': results,
                'timestamp': now()
            }
            
        except Exception as e:
            self.logger.error(f"Overdue contributions processing failed: {str(e)}")
            raise SchedulerServiceError(f"Processing failed: {str(e)}")
    
    def _get_overdue_contributions(self) -> List:
        """Get all overdue contributions that need processing"""
        try:
            # Get contributions that are unpaid and past due date
            overdue = frappe.get_all(
                "SHG Contribution",
                filters={
                    "status": "Unpaid",
                    "docstatus": 1,
                    "contribution_date": ["<", now().split()[0]],  # Before today
                    "custom_overdue_processed": ["!=", 1]  # Not already processed
                },
                fields=["name", "member", "member_name", "contribution_date", "expected_amount", "status"]
            )
            
            return overdue
            
        except Exception as e:
            self.logger.error(f"Failed to fetch overdue contributions: {str(e)}")
            raise
    
    def _process_overdue_contribution(self, contribution_data: Dict) -> Dict:
        """Process a single overdue contribution"""
        try:
            # Update contribution status to Overdue
            contribution = frappe.get_doc("SHG Contribution", contribution_data['name'])
            contribution.db_set("status", "Overdue")
            contribution.db_set("custom_overdue_processed", 1)
            
            # Update member financial summary
            from .member.member_service import member_service
            member_service.update_member_financial_summary(contribution.member)
            
            # Send overdue notification
            self._send_overdue_notification(contribution_data)
            
            return {
                'contribution': contribution_data['name'],
                'member': contribution_data['member'],
                'status': 'processed',
                'new_status': 'Overdue',
                'timestamp': now()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to process overdue contribution {contribution_data['name']}: {str(e)}")
            raise
    
    def _send_overdue_notification(self, contribution_data: Dict):
        """Send overdue notification to member"""
        try:
            from .notification.notification_service import notification_service
            
            message = f"""
            Dear {contribution_data['member_name']},
            
            This is a reminder that your contribution of KES {contribution_data['expected_amount']:,.2f} 
            dated {contribution_data['contribution_date']} is now overdue.
            
            Please make the payment at your earliest convenience to avoid further action.
            
            Thank you for your attention to this matter.
            
            SHG Management
            """
            
            notification_service.send_notification(
                contribution_data['member'],
                'Overdue Contribution',
                message,
                'SMS'
            )
            
        except Exception as e:
            self.logger.error(f"Failed to send overdue notification: {str(e)}")
            # Don't fail the main process if notification fails
    
    def process_monthly_statements(self) -> Dict:
        """
        Generate and send monthly statements to all members
        
        Returns:
            Dict with processing results
        """
        try:
            # Get all active members
            active_members = frappe.get_all(
                "SHG Member",
                filters={"membership_status": "Active", "docstatus": 1},
                fields=["name", "member_name", "email", "phone_number"]
            )
            
            if not active_members:
                return {
                    'status': 'success',
                    'processed_count': 0,
                    'message': 'No active members found',
                    'timestamp': now()
                }
            
            # Process each member
            processed_count = 0
            failed_count = 0
            results = []
            
            for member in active_members:
                try:
                    result = self._process_member_statement(member)
                    results.append(result)
                    processed_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to process statement for member {member.name}: {str(e)}")
                    failed_count += 1
                    results.append({
                        'member': member.name,
                        'status': 'failed',
                        'error': str(e)
                    })
            
            # Log completion
            self._log_scheduler_job(
                'monthly_statements',
                processed_count,
                failed_count,
                results
            )
            
            return {
                'status': 'completed',
                'total_members': len(active_members),
                'processed_count': processed_count,
                'failed_count': failed_count,
                'results': results,
                'timestamp': now()
            }
            
        except Exception as e:
            self.logger.error(f"Monthly statements processing failed: {str(e)}")
            raise SchedulerServiceError(f"Processing failed: {str(e)}")
    
    def _process_member_statement(self, member_data: Dict) -> Dict:
        """Process monthly statement for a single member"""
        try:
            # Generate statement data
            statement_data = self._generate_member_statement(member_data['name'])
            
            # Send statement via email
            self._send_member_statement(member_data, statement_data)
            
            return {
                'member': member_data['name'],
                'member_name': member_data['member_name'],
                'status': 'processed',
                'statement_period': statement_data.get('period', 'N/A'),
                'timestamp': now()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to process member statement {member_data['name']}: {str(e)}")
            raise
    
    def _generate_member_statement(self, member_id: str) -> Dict:
        """Generate member statement data"""
        try:
            from datetime import datetime
            from frappe.utils import get_first_day, get_last_day
            
            # Get current month period
            today = getdate()
            first_day = get_first_day(today)
            last_day = get_last_day(today)
            
            # Get contributions for the period
            contributions = frappe.get_all(
                "SHG Contribution",
                filters={
                    "member": member_id,
                    "contribution_date": ["between", [first_day, last_day]],
                    "docstatus": 1
                },
                fields=["contribution_date", "expected_amount", "amount_paid", "status"]
            )
            
            # Get payments for the period
            payments = frappe.get_all(
                "Payment Entry",
                filters={
                    "party_type": "SHG Member",
                    "party": member_id,
                    "posting_date": ["between", [first_day, last_day]],
                    "docstatus": 1
                },
                fields=["posting_date", "paid_amount"]
            )
            
            # Calculate totals
            total_expected = sum(c.expected_amount or c.amount for c in contributions)
            total_paid = sum(c.amount_paid for c in contributions)
            total_payments = sum(p.paid_amount for p in payments)
            
            return {
                'period': f"{first_day} to {last_day}",
                'member_id': member_id,
                'contributions': contributions,
                'payments': payments,
                'total_expected': total_expected,
                'total_paid': total_paid,
                'total_payments': total_payments,
                'balance': total_expected - total_paid,
                'generated_date': now()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate member statement: {str(e)}")
            raise
    
    def _send_member_statement(self, member_data: Dict, statement_data: Dict):
        """Send member statement via email"""
        try:
            from .notification.notification_service import notification_service
            
            # Format statement as HTML
            statement_html = self._format_statement_html(member_data, statement_data)
            
            # Send email
            notification_service.send_notification(
                member_data['name'],
                'Monthly Statement',
                statement_html,
                'Email'
            )
            
        except Exception as e:
            self.logger.error(f"Failed to send member statement: {str(e)}")
            raise
    
    def _format_statement_html(self, member_data: Dict, statement_data: Dict) -> str:
        """Format statement data as HTML email"""
        # This is a simplified HTML template
        # In production, you might want to use a proper template engine
        html = f"""
        <html>
        <body>
            <h2>Monthly Statement - {statement_data['period']}</h2>
            <p>Dear {member_data['member_name']},</p>
            
            <h3>Statement Summary</h3>
            <table border="1">
                <tr><td>Total Expected</td><td>KES {statement_data['total_expected']:,.2f}</td></tr>
                <tr><td>Total Paid</td><td>KES {statement_data['total_paid']:,.2f}</td></tr>
                <tr><td>Payments Received</td><td>KES {statement_data['total_payments']:,.2f}</td></tr>
                <tr><td>Outstanding Balance</td><td>KES {statement_data['balance']:,.2f}</td></tr>
            </table>
            
            <p>Thank you for your continued membership.</p>
            <p>SHG Management</p>
        </body>
        </html>
        """
        return html
    
    def process_payment_reminders(self) -> Dict:
        """
        Send payment reminders for upcoming due dates
        
        Returns:
            Dict with processing results
        """
        try:
            # Get upcoming due invoices (due in next 7 days)
            upcoming_due_date = add_days(getdate(), 7)
            
            upcoming_invoices = frappe.get_all(
                "SHG Contribution Invoice",
                filters={
                    "docstatus": 1,
                    "status": ["in", ["Unpaid", "Partially Paid"]],
                    "due_date": ["between", [getdate(), upcoming_due_date]]
                },
                fields=["name", "member", "member_name", "due_date", "amount"]
            )
            
            if not upcoming_invoices:
                return {
                    'status': 'success',
                    'processed_count': 0,
                    'message': 'No upcoming due invoices found',
                    'timestamp': now()
                }
            
            # Process each invoice
            processed_count = 0
            failed_count = 0
            results = []
            
            for invoice in upcoming_invoices:
                try:
                    result = self._send_payment_reminder(invoice)
                    results.append(result)
                    processed_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to send reminder for invoice {invoice.name}: {str(e)}")
                    failed_count += 1
                    results.append({
                        'invoice': invoice.name,
                        'status': 'failed',
                        'error': str(e)
                    })
            
            # Log completion
            self._log_scheduler_job(
                'payment_reminders',
                processed_count,
                failed_count,
                results
            )
            
            return {
                'status': 'completed',
                'total_invoices': len(upcoming_invoices),
                'processed_count': processed_count,
                'failed_count': failed_count,
                'results': results,
                'timestamp': now()
            }
            
        except Exception as e:
            self.logger.error(f"Payment reminders processing failed: {str(e)}")
            raise SchedulerServiceError(f"Processing failed: {str(e)}")
    
    def _send_payment_reminder(self, invoice_data: Dict) -> Dict:
        """Send payment reminder for a specific invoice"""
        try:
            from .notification.notification_service import notification_service
            
            message = f"""
            Dear {invoice_data['member_name']},
            
            This is a friendly reminder that your contribution payment of KES {invoice_data['amount']:,.2f} 
            is due on {invoice_data['due_date']}.
            
            Please ensure payment is made by the due date to avoid late fees.
            
            Thank you for your prompt attention to this matter.
            
            SHG Management
            """
            
            notification_service.send_notification(
                invoice_data['member'],
                'Payment Reminder',
                message,
                'SMS'
            )
            
            return {
                'invoice': invoice_data['name'],
                'member': invoice_data['member'],
                'due_date': str(invoice_data['due_date']),
                'amount': invoice_data['amount'],
                'status': 'reminder_sent',
                'timestamp': now()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to send payment reminder: {str(e)}")
            raise
    
    def _log_scheduler_job(self, job_type: str, success_count: int, 
                          failure_count: int, results: List[Dict]):
        """Log scheduler job execution for audit trail"""
        try:
            log_entry = frappe.get_doc({
                'doctype': 'SHG Scheduler Log',
                'job_type': job_type,
                'success_count': success_count,
                'failure_count': failure_count,
                'total_processed': success_count + failure_count,
                'results': json.dumps(results),
                'execution_time': now()
            })
            log_entry.insert(ignore_permissions=True)
            
        except Exception as e:
            self.logger.error(f"Failed to log scheduler job: {str(e)}")
    
    def get_scheduler_status(self) -> Dict:
        """
        Get current status of scheduler jobs
        
        Returns:
            Dict with scheduler status information
        """
        try:
            # Get recent job logs
            recent_logs = frappe.get_all(
                "SHG Scheduler Log",
                fields=["job_type", "execution_time", "success_count", "failure_count"],
                order_by="execution_time desc",
                limit=10
            )
            
            # Get pending jobs
            pending_jobs = self._get_pending_jobs()
            
            return {
                'recent_executions': recent_logs,
                'pending_jobs': pending_jobs,
                'system_status': 'operational',
                'last_updated': now()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get scheduler status: {str(e)}")
            return {
                'system_status': 'error',
                'error': str(e),
                'last_updated': now()
            }
    
    def _get_pending_jobs(self) -> List[Dict]:
        """Get list of pending/queued jobs"""
        # This would integrate with your job queue system
        # For now, return empty list
        return []

# Global service instance
scheduler_service = SchedulerService()