"""
Notification Service Layer
Enterprise-grade notification service with multiple channels and structured logging
"""
import frappe
from frappe import _
from frappe.utils import now
from typing import Dict, List, Optional, Union
import json
import logging
from datetime import datetime

class NotificationServiceError(Exception):
    """Base exception for notification service errors"""
    pass

class NotificationService:
    """
    Enterprise-grade notification service with:
    - Multiple channel support (SMS, Email, WhatsApp)
    - Structured logging
    - Retry mechanisms
    - Audit trail
    - Configurable templates
    """
    
    def __init__(self):
        self.logger = frappe.logger("notification_service", allow_site=True)
        self.setup_logging()
    
    def setup_logging(self):
        """Setup structured logging for notifications"""
        # Configure logging format for better audit trail
        pass  # Frappe logger handles this
    
    def send_notification(self, member_id: str, notification_type: str, 
                         message: str, channel: str = "SMS", 
                         reference_document: Optional[str] = None,
                         reference_name: Optional[str] = None) -> Dict:
        """
        Send notification through specified channel
        
        Args:
            member_id: Member ID to send notification to
            notification_type: Type of notification
            message: Notification message
            channel: Communication channel (SMS, Email, WhatsApp)
            reference_document: Related document type
            reference_name: Related document name
            
        Returns:
            Dict with notification result and log reference
        """
        try:
            # Validate inputs
            self._validate_notification_inputs(member_id, notification_type, message, channel)
            
            # Get member contact information
            member_contact = self._get_member_contact(member_id, channel)
            
            # Send notification through appropriate channel
            notification_result = self._send_via_channel(
                member_contact, 
                message, 
                channel,
                notification_type
            )
            
            # Log notification
            log_entry = self._log_notification(
                member_id, 
                notification_type, 
                message, 
                channel, 
                notification_result,
                reference_document,
                reference_name
            )
            
            return {
                'status': 'success',
                'notification_id': log_entry.name,
                'channel': channel,
                'recipient': member_contact.get('contact'),
                'timestamp': now(),
                'result': notification_result
            }
            
        except Exception as e:
            error_result = self._handle_notification_error(
                member_id, notification_type, message, channel, str(e)
            )
            raise NotificationServiceError(f"Notification failed: {str(e)}")
    
    def _validate_notification_inputs(self, member_id: str, notification_type: str, 
                                   message: str, channel: str):
        """Validate notification inputs"""
        if not member_id:
            raise NotificationServiceError("Member ID is required")
        
        if not notification_type:
            raise NotificationServiceError("Notification type is required")
        
        if not message:
            raise NotificationServiceError("Message content is required")
        
        if channel not in ['SMS', 'Email', 'WhatsApp']:
            raise NotificationServiceError(f"Unsupported channel: {channel}")
    
    def _get_member_contact(self, member_id: str, channel: str) -> Dict:
        """Get member contact information for specified channel"""
        try:
            member = frappe.get_doc("SHG Member", member_id)
            
            contact_info = {
                'member_id': member_id,
                'member_name': member.member_name
            }
            
            if channel == 'SMS':
                if not member.phone_number:
                    raise NotificationServiceError(f"Member {member_id} has no phone number")
                contact_info['contact'] = member.phone_number
                contact_info['contact_type'] = 'phone'
                
            elif channel == 'Email':
                if not member.email:
                    raise NotificationServiceError(f"Member {member_id} has no email address")
                contact_info['contact'] = member.email
                contact_info['contact_type'] = 'email'
                
            elif channel == 'WhatsApp':
                # Use phone number for WhatsApp
                if not member.phone_number:
                    raise NotificationServiceError(f"Member {member_id} has no phone number for WhatsApp")
                contact_info['contact'] = member.phone_number
                contact_info['contact_type'] = 'whatsapp'
            
            return contact_info
            
        except frappe.DoesNotExistError:
            raise NotificationServiceError(f"Member {member_id} not found")
    
    def _send_via_channel(self, member_contact: Dict, message: str, 
                         channel: str, notification_type: str) -> Dict:
        """Send notification through the specified channel"""
        if channel == 'SMS':
            return self._send_sms(member_contact, message, notification_type)
        elif channel == 'Email':
            return self._send_email(member_contact, message, notification_type)
        elif channel == 'WhatsApp':
            return self._send_whatsapp(member_contact, message, notification_type)
        else:
            raise NotificationServiceError(f"Unsupported channel: {channel}")
    
    def _send_sms(self, member_contact: Dict, message: str, notification_type: str) -> Dict:
        """Send SMS notification"""
        try:
            phone_number = member_contact['contact']
            
            # Use ERPNext SMS settings or custom integration
            # This is a placeholder - implement based on your SMS provider
            sms_result = self._send_sms_via_provider(phone_number, message)
            
            self.logger.info(f"SMS sent to {phone_number}", 
                           extra={'member': member_contact['member_id'], 
                                 'type': notification_type,
                                 'result': sms_result})
            
            return {
                'provider': 'SMS Gateway',
                'message_id': sms_result.get('message_id', 'N/A'),
                'status': 'sent',
                'timestamp': now()
            }
            
        except Exception as e:
            self.logger.error(f"SMS sending failed: {str(e)}")
            raise
    
    def _send_sms_via_provider(self, phone_number: str, message: str) -> Dict:
        """Send SMS via actual provider (implement based on your setup)"""
        # This should be implemented with your actual SMS provider
        # Example for different providers:
        
        # For generic SMS API:
        # import requests
        # response = requests.post(sms_api_url, data={
        #     'to': phone_number,
        #     'message': message,
        #     'api_key': 'your_api_key'
        # })
        # return response.json()
        
        # For Twilio:
        # from twilio.rest import Client
        # client = Client(account_sid, auth_token)
        # message = client.messages.create(
        #     body=message,
        #     from_=from_phone,
        #     to=phone_number
        # )
        # return {'message_id': message.sid}
        
        # Placeholder return
        return {'message_id': f'sms_{now().replace(" ", "_")}_{phone_number[-4:]}'}
    
    def _send_email(self, member_contact: Dict, message: str, notification_type: str) -> Dict:
        """Send Email notification"""
        try:
            email_address = member_contact['contact']
            member_name = member_contact['member_name']
            
            # Prepare email content
            subject = self._get_email_subject(notification_type, member_name)
            email_message = self._format_email_message(message, member_name)
            
            # Send email using Frappe
            frappe.sendmail(
                recipients=[email_address],
                subject=subject,
                message=email_message,
                reference_doctype="SHG Member",
                reference_name=member_contact['member_id']
            )
            
            self.logger.info(f"Email sent to {email_address}",
                           extra={'member': member_contact['member_id'],
                                 'type': notification_type,
                                 'subject': subject})
            
            return {
                'provider': 'Frappe Email',
                'status': 'sent',
                'timestamp': now()
            }
            
        except Exception as e:
            self.logger.error(f"Email sending failed: {str(e)}")
            raise
    
    def _send_whatsapp(self, member_contact: Dict, message: str, notification_type: str) -> Dict:
        """Send WhatsApp notification"""
        try:
            phone_number = member_contact['contact']
            
            # WhatsApp sending logic (implement based on your provider)
            # This could use:
            # 1. Twilio WhatsApp API
            # 2. 360Dialog
            # 3. Gupshup
            # 4. Custom WhatsApp Business API integration
            
            whatsapp_result = self._send_whatsapp_via_provider(phone_number, message)
            
            self.logger.info(f"WhatsApp sent to {phone_number}",
                           extra={'member': member_contact['member_id'],
                                 'type': notification_type,
                                 'result': whatsapp_result})
            
            return {
                'provider': 'WhatsApp Business API',
                'message_id': whatsapp_result.get('message_id', 'N/A'),
                'status': 'sent',
                'timestamp': now()
            }
            
        except Exception as e:
            self.logger.error(f"WhatsApp sending failed: {str(e)}")
            raise
    
    def _send_whatsapp_via_provider(self, phone_number: str, message: str) -> Dict:
        """Send WhatsApp via provider (implement based on your setup)"""
        # Implement based on your WhatsApp provider
        # Placeholder return
        return {'message_id': f'whatsapp_{now().replace(" ", "_")}_{phone_number[-4:]}'}
    
    def _get_email_subject(self, notification_type: str, member_name: str) -> str:
        """Get appropriate email subject based on notification type"""
        subject_templates = {
            'Payment Reminder': f'Payment Reminder - {member_name}',
            'Payment Confirmation': f'Payment Confirmation - {member_name}',
            'Contribution Due': f'Contribution Due - {member_name}',
            'Meeting Reminder': f'Meeting Reminder - {member_name}',
            'Default': f'Notification for {member_name}'
        }
        
        return subject_templates.get(notification_type, subject_templates['Default'])
    
    def _format_email_message(self, message: str, member_name: str) -> str:
        """Format email message with proper HTML template"""
        html_template = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <div style="max-width: 600px; margin: 0 auto;">
                <h2 style="color: #2c3e50;">SHG Notification</h2>
                <p>Dear {member_name},</p>
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <p>{message}</p>
                </div>
                <p style="color: #6c757d; font-size: 14px;">
                    This is an automated message from your SHG system.
                </p>
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #dee2e6;">
                <p style="color: #6c757d; font-size: 12px;">
                    If you have any questions, please contact your SHG administrator.
                </p>
            </div>
        </body>
        </html>
        """
        return html_template
    
    def _log_notification(self, member_id: str, notification_type: str, message: str,
                         channel: str, result: Dict, reference_document: Optional[str] = None,
                         reference_name: Optional[str] = None) -> object:
        """Log notification for audit trail"""
        try:
            log_entry = frappe.get_doc({
                'doctype': 'SHG Notification Log',
                'member': member_id,
                'notification_type': notification_type,
                'channel': channel,
                'message': message,
                'status': result.get('status', 'sent'),
                'provider_response': json.dumps(result),
                'reference_document': reference_document,
                'reference_name': reference_name,
                'sent_on': now()
            })
            log_entry.insert(ignore_permissions=True)
            
            return log_entry
            
        except Exception as e:
            self.logger.error(f"Failed to log notification: {str(e)}")
            # Don't fail the main operation if logging fails
            return None
    
    def _handle_notification_error(self, member_id: str, notification_type: str, 
                                 message: str, channel: str, error: str) -> Dict:
        """Handle notification errors gracefully"""
        try:
            # Log error
            error_log = frappe.get_doc({
                'doctype': 'SHG Notification Log',
                'member': member_id,
                'notification_type': notification_type,
                'channel': channel,
                'message': message,
                'status': 'failed',
                'error_message': error,
                'sent_on': now()
            })
            error_log.insert(ignore_permissions=True)
            
            # Try fallback notification if configured
            self._attempt_fallback_notification(member_id, notification_type, message, channel, error)
            
            return {
                'status': 'failed',
                'error': error,
                'timestamp': now()
            }
            
        except Exception as e:
            self.logger.error(f"Error handling failed: {str(e)}")
            return {
                'status': 'failed',
                'error': f"{error}; Error handler also failed: {str(e)}",
                'timestamp': now()
            }
    
    def _attempt_fallback_notification(self, member_id: str, notification_type: str, 
                                      message: str, primary_channel: str, error: str):
        """Attempt fallback notification through alternative channels"""
        fallback_channels = self._get_fallback_channels(primary_channel)
        
        for channel in fallback_channels:
            try:
                self.logger.info(f"Attempting fallback notification via {channel}")
                self.send_notification(
                    member_id, 
                    notification_type, 
                    f"{message} [Fallback from {primary_channel} due to: {error}]", 
                    channel
                )
                break  # Stop after successful fallback
            except Exception as e:
                self.logger.error(f"Fallback notification via {channel} also failed: {str(e)}")
                continue
    
    def _get_fallback_channels(self, primary_channel: str) -> List[str]:
        """Get fallback channels in order of preference"""
        channel_priority = {
            'SMS': ['Email', 'WhatsApp'],
            'Email': ['SMS', 'WhatsApp'],
            'WhatsApp': ['SMS', 'Email']
        }
        return channel_priority.get(primary_channel, ['SMS', 'Email'])
    
    def send_bulk_notifications(self, members: List[str], notification_type: str,
                               message_template: str, channel: str = "SMS") -> Dict:
        """
        Send bulk notifications to multiple members
        
        Args:
            members: List of member IDs
            notification_type: Type of notification
            message_template: Message template with placeholders
            channel: Communication channel
            
        Returns:
            Dict with bulk notification results
        """
        results = {
            'total': len(members),
            'successful': 0,
            'failed': 0,
            'results': []
        }
        
        for member_id in members:
            try:
                # Personalize message
                member = frappe.get_doc("SHG Member", member_id)
                personalized_message = message_template.format(
                    member_name=member.member_name,
                    member_id=member_id
                )
                
                # Send notification
                result = self.send_notification(
                    member_id, 
                    notification_type, 
                    personalized_message, 
                    channel
                )
                results['successful'] += 1
                results['results'].append(result)
                
            except Exception as e:
                results['failed'] += 1
                results['results'].append({
                    'member': member_id,
                    'status': 'failed',
                    'error': str(e)
                })
                self.logger.error(f"Bulk notification failed for {member_id}: {str(e)}")
        
        return results
    
    def get_notification_history(self, member_id: str, 
                                from_date: Optional[str] = None,
                                to_date: Optional[str] = None) -> List[Dict]:
        """
        Get notification history for a member
        
        Args:
            member_id: Member ID
            from_date: Optional start date
            to_date: Optional end date
            
        Returns:
            List of notification records
        """
        try:
            filters = {"member": member_id}
            if from_date:
                filters["sent_on"] = [">=", from_date]
            if to_date:
                filters["sent_on"] = ["<=", to_date]
            
            return frappe.get_all(
                "SHG Notification Log",
                filters=filters,
                fields=["notification_type", "channel", "message", "status", "sent_on"],
                order_by="sent_on desc"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to fetch notification history: {str(e)}")
            return []

# Global service instance
notification_service = NotificationService()