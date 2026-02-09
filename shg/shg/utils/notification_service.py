import frappe
from frappe.utils import now, getdate, add_days
import json
import requests
from typing import Dict, List, Optional, Union

class NotificationService:
    """
    Comprehensive notification service supporting SMS, Email, and WhatsApp
    """
    
    def __init__(self):
        self.settings = frappe.get_single("SHG Settings")
    
    def send_notification(
        self, 
        member_id: str, 
        notification_type: str, 
        message: str, 
        channel: str = "SMS",
        reference_document: str = None,
        reference_name: str = None,
        custom_data: dict = None
    ) -> Dict:
        """
        Send notification to a member via specified channel
        
        Args:
            member_id: ID of the member to notify
            notification_type: Type of notification (e.g., "Payment Confirmation")
            message: Content of the notification
            channel: Channel to use ("SMS", "Email", "WhatsApp", "Push Notification")
            reference_document: Reference document type
            reference_name: Reference document name
            custom_data: Additional data for the notification
        
        Returns:
            Dict containing status and result
        """
        try:
            # Get member details
            member = frappe.get_doc("SHG Member", member_id)
            
            # Create notification log
            notification_log = frappe.get_doc({
                "doctype": "SHG Notification Log",
                "member": member_id,
                "member_name": member.member_name,
                "notification_type": notification_type,
                "channel": channel,
                "message": message,
                "reference_document": reference_document,
                "reference_name": reference_name,
                "status": "Pending"
            })
            notification_log.insert(ignore_permissions=True)
            
            # Send notification based on channel
            if channel == "SMS":
                result = self._send_sms(member, message, notification_log.name)
            elif channel == "Email":
                result = self._send_email(member, notification_type, message, notification_log.name)
            elif channel == "WhatsApp":
                result = self._send_whatsapp(member, message, notification_log.name)
            elif channel == "Push Notification":
                result = self._send_push_notification(member, notification_type, message, custom_data, notification_log.name)
            else:
                raise ValueError(f"Unsupported channel: {channel}")
            
            # Update notification log with result
            self._update_notification_log(notification_log.name, result)
            
            return {
                "status": "success",
                "notification_log_id": notification_log.name,
                "result": result
            }
            
        except Exception as e:
            frappe.log_error(
                f"Failed to send notification to member {member_id}",
                "SHG Notification Service Error"
            )
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _send_sms(self, member: object, message: str, notification_log_id: str) -> Dict:
        """
        Send SMS using configured gateway (Africa's Talking or other)
        """
        try:
            # Check if SMS is enabled in settings
            if not self.settings.sms_enabled:
                return {"status": "skipped", "reason": "SMS not enabled in settings"}
            
            # Get member phone number
            phone_number = getattr(member, "phone_number", None)
            if not phone_number:
                return {"status": "failed", "reason": "No phone number available"}
            
            # Normalize phone number (ensure it's in international format)
            phone_number = self._normalize_phone_number(phone_number)
            
            # Determine SMS provider based on settings
            if hasattr(self.settings, 'sms_provider') and self.settings.sms_provider == "Africa's Talking":
                result = self._send_via_africas_talking(phone_number, message)
            else:
                # Default to generic SMS provider
                result = self._send_via_generic_sms(phone_number, message)
            
            return result
            
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def _send_via_africas_talking(self, phone_number: str, message: str) -> Dict:
        """
        Send SMS via Africa's Talking API
        """
        try:
            username = self.settings.sms_username
            api_key = self.settings.get_password("sms_api_key")
            sender_id = self.settings.sms_sender_id or "SHG"
            
            url = "https://api.africastalking.com/version1/messaging"
            
            headers = {
                "apikey": api_key,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }
            
            data = {
                "username": username,
                "to": phone_number,
                "message": message,
                "from": sender_id
            }
            
            response = requests.post(url, headers=headers, data=data)
            
            if response.status_code == 201:
                response_data = response.json()
                if response_data.get("SMSMessageData", {}).get("Recipients"):
                    return {
                        "status": "sent",
                        "response": response_data,
                        "provider": "Africa's Talking"
                    }
                else:
                    return {
                        "status": "failed",
                        "error": "Message not delivered",
                        "response": response_data
                    }
            else:
                return {
                    "status": "failed",
                    "error": f"API returned status {response.status_code}",
                    "response": response.text
                }
                
        except Exception as e:
            return {
                "status": "failed", 
                "error": str(e)
            }
    
    def _send_via_generic_sms(self, phone_number: str, message: str) -> Dict:
        """
        Generic SMS sending method (can be extended for other providers)
        """
        # For now, just simulate sending (in production, connect to actual SMS gateway)
        frappe.log_error(
            f"SIMULATION: Would send SMS to {phone_number}: {message}",
            "SHG SMS Simulation"
        )
        return {
            "status": "sent",
            "simulated": True,
            "phone_number": phone_number,
            "message": message
        }
    
    def _send_email(self, member: object, subject: str, message: str, notification_log_id: str) -> Dict:
        """
        Send email to member
        """
        try:
            # Get member email
            email = getattr(member, "email", None)
            if not email:
                return {"status": "failed", "reason": "No email address available"}
            
            # Send email using Frappe's built-in email functionality
            frappe.sendmail(
                recipients=[email],
                subject=subject,
                message=message,
                delayed=False  # Send immediately
            )
            
            return {
                "status": "sent",
                "email": email,
                "recipients": [email]
            }
            
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def _send_whatsapp(self, member: object, message: str, notification_log_id: str) -> Dict:
        """
        Send WhatsApp message (requires WhatsApp Business API)
        """
        try:
            phone_number = getattr(member, "phone_number", None)
            if not phone_number:
                return {"status": "failed", "reason": "No phone number available"}
            
            # Normalize phone number
            phone_number = self._normalize_phone_number(phone_number, whatsapp_format=True)
            
            # Check if WhatsApp Business API is configured
            whatsapp_configured = (
                hasattr(self.settings, 'whatsapp_business_token') and 
                self.settings.whatsapp_business_token
            )
            
            if whatsapp_configured:
                result = self._send_via_whatsapp_business_api(phone_number, message)
            else:
                # Simulate WhatsApp sending
                frappe.log_error(
                    f"SIMULATION: Would send WhatsApp to {phone_number}: {message}",
                    "SHG WhatsApp Simulation"
                )
                result = {
                    "status": "sent",
                    "simulated": True,
                    "phone_number": phone_number,
                    "message": message
                }
            
            return result
            
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def _send_via_whatsapp_business_api(self, phone_number: str, message: str) -> Dict:
        """
        Send message via WhatsApp Business API
        """
        try:
            # This is a template - actual implementation would depend on specific provider
            access_token = self.settings.get_password("whatsapp_business_token")
            phone_number_id = self.settings.whatsapp_phone_number_id  # Configured in settings
            
            url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "text",
                "text": {
                    "body": message
                }
            }
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                response_data = response.json()
                return {
                    "status": "sent",
                    "response": response_data,
                    "provider": "WhatsApp Business API"
                }
            else:
                return {
                    "status": "failed",
                    "error": f"API returned status {response.status_code}",
                    "response": response.text
                }
                
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def _send_push_notification(self, member: object, title: str, message: str, custom_data: dict, notification_log_id: str) -> Dict:
        """
        Send push notification to mobile app
        """
        try:
            # For now, simulate push notification
            # In production, this would connect to Firebase Cloud Messaging or similar
            frappe.log_error(
                f"SIMULATION: Would send push notification to member {member.name}: {title} - {message}",
                "SHG Push Notification Simulation"
            )
            
            return {
                "status": "sent",
                "simulated": True,
                "member": member.name,
                "title": title,
                "message": message
            }
            
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def _normalize_phone_number(self, phone: str, whatsapp_format: bool = False) -> str:
        """
        Normalize phone number to international format
        """
        if not phone:
            return phone
            
        # Remove any non-digit characters
        phone = ''.join(filter(str.isdigit, phone))
        
        # Handle different formats
        if phone.startswith('0'):
            # Convert Kenyan 07xxx to +2547xxx
            phone = '+254' + phone[1:]
        elif phone.startswith('7') and len(phone) == 9:
            # Add country code to 7xxxxxxx
            phone = '+254' + phone
        elif phone.startswith('254') and len(phone) == 12:
            # Add + to 254xxxxxxxx
            phone = '+' + phone
        elif phone.startswith('+') and phone[1:].startswith('254'):
            # Already in correct format
            pass
        else:
            # Assume it's already in international format or leave as is
            pass
        
        # For WhatsApp, sometimes need to remove the +
        if whatsapp_format and phone.startswith('+'):
            phone = phone[1:]
            
        return phone
    
    def _update_notification_log(self, notification_log_id: str, result: Dict):
        """
        Update notification log with result
        """
        try:
            notification_log = frappe.get_doc("SHG Notification Log", notification_log_id)
            
            if result["status"] == "sent":
                notification_log.status = "Sent"
                notification_log.sent_date = now()
            elif result["status"] == "delivered":
                notification_log.status = "Delivered"
                notification_log.delivery_status = "Delivered"
            elif result["status"] == "failed":
                notification_log.status = "Failed"
                notification_log.error_message = result.get("error", "Unknown error")
            elif result["status"] == "skipped":
                notification_log.status = "Failed"
                notification_log.error_message = result.get("reason", "Skipped")
            
            notification_log.delivery_status = result.get("status", notification_log.status)
            notification_log.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(
                f"Failed to update notification log {notification_log_id}",
                "SHG Notification Service Error"
            )
    
    def send_batch_notifications(
        self, 
        members: List[str], 
        notification_type: str, 
        message_template: str,
        channel: str = "SMS",
        reference_document: str = None,
        reference_name: str = None
    ) -> Dict:
        """
        Send batch notifications to multiple members
        
        Args:
            members: List of member IDs
            notification_type: Type of notification
            message_template: Message template with placeholders (e.g., "Hello {member_name}")
            channel: Channel to use
            reference_document: Reference document type
            reference_name: Reference document name
        
        Returns:
            Dict with summary of results
        """
        results = {
            "sent": 0,
            "failed": 0,
            "total": len(members),
            "details": []
        }
        
        for member_id in members:
            try:
                # Get member to personalize message
                member = frappe.get_doc("SHG Member", member_id)
                
                # Personalize message
                personalized_message = message_template.format(
                    member_name=getattr(member, "member_name", "Member"),
                    phone_number=getattr(member, "phone_number", ""),
                    email=getattr(member, "email", ""),
                    id_number=getattr(member, "id_number", "")
                )
                
                result = self.send_notification(
                    member_id=member_id,
                    notification_type=notification_type,
                    message=personalized_message,
                    channel=channel,
                    reference_document=reference_document,
                    reference_name=reference_name
                )
                
                if result["status"] == "success":
                    results["sent"] += 1
                else:
                    results["failed"] += 1
                    
                results["details"].append({
                    "member_id": member_id,
                    "result": result
                })
                
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "member_id": member_id,
                    "result": {"status": "error", "error": str(e)}
                })
        
        return results
    
    def schedule_notification(
        self,
        member_id: str,
        notification_type: str,
        message: str,
        scheduled_date: str,
        channel: str = "SMS",
        reference_document: str = None,
        reference_name: str = None
    ) -> str:
        """
        Schedule a notification to be sent at a later date
        
        Args:
            member_id: ID of the member to notify
            notification_type: Type of notification
            message: Content of the notification
            scheduled_date: Date when notification should be sent
            channel: Channel to use
            reference_document: Reference document type
            reference_name: Reference document name
        
        Returns:
            Scheduled notification ID
        """
        # Create a scheduled notification document
        scheduled_notification = frappe.get_doc({
            "doctype": "SHG Scheduled Notification",
            "member": member_id,
            "notification_type": notification_type,
            "message": message,
            "scheduled_date": scheduled_date,
            "channel": channel,
            "reference_document": reference_document,
            "reference_name": reference_name,
            "status": "Scheduled"
        })
        
        scheduled_notification.insert(ignore_permissions=True)
        return scheduled_notification.name
    
    def process_scheduled_notifications(self):
        """
        Process all scheduled notifications that are due
        This method would typically be called by a scheduled job
        """
        from frappe.utils import today
        
        # Get all scheduled notifications that are due (today or earlier)
        due_notifications = frappe.get_all(
            "SHG Scheduled Notification",
            filters={
                "scheduled_date": ["<=", today()],
                "status": "Scheduled"
            },
            fields=["name", "member", "notification_type", "message", "channel", "reference_document", "reference_name"]
        )
        
        results = {
            "processed": 0,
            "successful": 0,
            "failed": 0
        }
        
        for notification in due_notifications:
            try:
                # Send the notification
                result = self.send_notification(
                    member_id=notification["member"],
                    notification_type=notification["notification_type"],
                    message=notification["message"],
                    channel=notification["channel"],
                    reference_document=notification["reference_document"],
                    reference_name=notification["reference_name"]
                )
                
                # Update the scheduled notification
                sched_doc = frappe.get_doc("SHG Scheduled Notification", notification["name"])
                if result["status"] == "success":
                    sched_doc.status = "Sent"
                    sched_doc.notification_log = result.get("notification_log_id")
                    results["successful"] += 1
                else:
                    sched_doc.status = "Failed"
                    sched_doc.error_message = result.get("error", "Unknown error")
                    results["failed"] += 1
                
                sched_doc.save(ignore_permissions=True)
                results["processed"] += 1
                
            except Exception as e:
                frappe.log_error(
                    f"Failed to process scheduled notification {notification['name']}",
                    "SHG Scheduled Notification Error"
                )
                results["failed"] += 1
        
        return results

# Global functions for easy access
def send_notification(
    member_id: str, 
    notification_type: str, 
    message: str, 
    channel: str = "SMS",
    reference_document: str = None,
    reference_name: str = None
) -> Dict:
    """
    Convenience function to send a notification
    """
    service = NotificationService()
    return service.send_notification(
        member_id=member_id,
        notification_type=notification_type,
        message=message,
        channel=channel,
        reference_document=reference_document,
        reference_name=reference_name
    )

def send_batch_notifications(
    members: List[str], 
    notification_type: str, 
    message_template: str,
    channel: str = "SMS",
    reference_document: str = None,
    reference_name: str = None
) -> Dict:
    """
    Convenience function to send batch notifications
    """
    service = NotificationService()
    return service.send_batch_notifications(
        members=members,
        notification_type=notification_type,
        message_template=message_template,
        channel=channel,
        reference_document=reference_document,
        reference_name=reference_name
    )

def schedule_notification(
    member_id: str,
    notification_type: str,
    message: str,
    scheduled_date: str,
    channel: str = "SMS",
    reference_document: str = None,
    reference_name: str = None
) -> str:
    """
    Convenience function to schedule a notification
    """
    service = NotificationService()
    return service.schedule_notification(
        member_id=member_id,
        notification_type=notification_type,
        message=message,
        scheduled_date=scheduled_date,
        channel=channel,
        reference_document=reference_document,
        reference_name=reference_name
    )


def process_scheduled_notifications():
    """
    Convenience function to process all scheduled notifications
    This function is designed to be called by the scheduler
    """
    service = NotificationService()
    return service.process_scheduled_notifications()
