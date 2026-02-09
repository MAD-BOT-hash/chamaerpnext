import frappe
from frappe import _
from frappe.utils.response import json_handler
from shg.shg.utils.notification_service import (
    send_notification,
    send_batch_notifications,
    schedule_notification,
    NotificationService
)
import json

@frappe.whitelist(allow_guest=False)
def send_member_notification():
    """
    Send notification to a specific member
    
    Required params:
    - member_id: ID of the member
    - notification_type: Type of notification
    - message: Content of the message
    - channel: Channel to use (SMS, Email, WhatsApp, Push Notification)
    
    Optional params:
    - reference_document: Reference document type
    - reference_name: Reference document name
    """
    try:
        # Get parameters from form dict
        member_id = frappe.form_dict.get('member_id')
        notification_type = frappe.form_dict.get('notification_type')
        message = frappe.form_dict.get('message')
        channel = frappe.form_dict.get('channel', 'SMS')
        reference_document = frappe.form_dict.get('reference_document')
        reference_name = frappe.form_dict.get('reference_name')
        
        # Validate required parameters
        if not member_id:
            return {
                "status": "error",
                "message": "Member ID is required"
            }
        
        if not notification_type:
            return {
                "status": "error", 
                "message": "Notification type is required"
            }
        
        if not message:
            return {
                "status": "error",
                "message": "Message is required"
            }
        
        # Send notification using the service
        result = send_notification(
            member_id=member_id,
            notification_type=notification_type,
            message=message,
            channel=channel,
            reference_document=reference_document,
            reference_name=reference_name
        )
        
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG API - Send Member Notification Error")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False)
def get_member_notifications():
    """
    Get notifications for a specific member
    
    Required params:
    - member_id: ID of the member
    - limit: Number of notifications to return (default 20)
    - offset: Offset for pagination (default 0)
    """
    try:
        member_id = frappe.form_dict.get('member_id')
        limit = int(frappe.form_dict.get('limit', 20))
        offset = int(frappe.form_dict.get('offset', 0))
        
        if not member_id:
            return {
                "status": "error",
                "message": "Member ID is required"
            }
        
        # Get notifications for the member
        notifications = frappe.get_all(
            "SHG Notification Log",
            filters={"member": member_id},
            fields=[
                "name", "member", "member_name", "notification_type", 
                "channel", "status", "sent_date", "message", 
                "reference_document", "reference_name", "delivery_status"
            ],
            order_by="creation DESC",
            limit_page_length=limit,
            limit_start=offset
        )
        
        return {
            "status": "success",
            "data": notifications,
            "count": len(notifications)
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG API - Get Member Notifications Error")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False)
def schedule_member_notification():
    """
    Schedule a notification to be sent at a later date
    
    Required params:
    - member_id: ID of the member
    - notification_type: Type of notification
    - message: Content of the message
    - scheduled_date: Date when notification should be sent (YYYY-MM-DD)
    - channel: Channel to use (SMS, Email, WhatsApp, Push Notification)
    
    Optional params:
    - reference_document: Reference document type
    - reference_name: Reference document name
    """
    try:
        # Get parameters from form dict
        member_id = frappe.form_dict.get('member_id')
        notification_type = frappe.form_dict.get('notification_type')
        message = frappe.form_dict.get('message')
        scheduled_date = frappe.form_dict.get('scheduled_date')
        channel = frappe.form_dict.get('channel', 'SMS')
        reference_document = frappe.form_dict.get('reference_document')
        reference_name = frappe.form_dict.get('reference_name')
        
        # Validate required parameters
        if not member_id:
            return {
                "status": "error",
                "message": "Member ID is required"
            }
        
        if not notification_type:
            return {
                "status": "error",
                "message": "Notification type is required"
            }
        
        if not message:
            return {
                "status": "error",
                "message": "Message is required"
            }
        
        if not scheduled_date:
            return {
                "status": "error",
                "message": "Scheduled date is required"
            }
        
        # Schedule notification
        scheduled_id = schedule_notification(
            member_id=member_id,
            notification_type=notification_type,
            message=message,
            scheduled_date=scheduled_date,
            channel=channel,
            reference_document=reference_document,
            reference_name=reference_name
        )
        
        return {
            "status": "success",
            "scheduled_id": scheduled_id
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG API - Schedule Member Notification Error")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False)
def get_scheduled_notifications():
    """
    Get scheduled notifications for a member or all scheduled notifications
    
    Optional params:
    - member_id: ID of the member (to get only member's scheduled notifications)
    - status: Filter by status (Scheduled, Sent, Failed)
    - limit: Number of notifications to return (default 20)
    - offset: Offset for pagination (default 0)
    """
    try:
        member_id = frappe.form_dict.get('member_id')
        status = frappe.form_dict.get('status')
        limit = int(frappe.form_dict.get('limit', 20))
        offset = int(frappe.form_dict.get('offset', 0))
        
        # Build filters
        filters = {}
        if member_id:
            filters["member"] = member_id
        if status:
            filters["status"] = status
        
        # Get scheduled notifications
        scheduled_notifications = frappe.get_all(
            "SHG Scheduled Notification",
            filters=filters,
            fields=[
                "name", "member", "member_name", "notification_type",
                "channel", "status", "scheduled_date", "message",
                "reference_document", "reference_name", "creation"
            ],
            order_by="scheduled_date ASC, creation DESC",
            limit_page_length=limit,
            limit_start=offset
        )
        
        return {
            "status": "success",
            "data": scheduled_notifications,
            "count": len(scheduled_notifications)
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG API - Get Scheduled Notifications Error")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False)
def send_batch_notifications_api():
    """
    Send notifications to multiple members at once
    
    Required params:
    - members: JSON string of member IDs list
    - notification_type: Type of notification
    - message_template: Message template with placeholders
    - channel: Channel to use (SMS, Email, WhatsApp, Push Notification)
    
    Optional params:
    - reference_document: Reference document type
    - reference_name: Reference document name
    """
    try:
        # Get parameters from form dict
        members_json = frappe.form_dict.get('members')
        notification_type = frappe.form_dict.get('notification_type')
        message_template = frappe.form_dict.get('message_template')
        channel = frappe.form_dict.get('channel', 'SMS')
        reference_document = frappe.form_dict.get('reference_document')
        reference_name = frappe.form_dict.get('reference_name')
        
        # Parse members JSON
        try:
            members = json.loads(members_json) if isinstance(members_json, str) else members_json
        except json.JSONDecodeError:
            return {
                "status": "error",
                "message": "Invalid members JSON format"
            }
        
        # Validate required parameters
        if not members or not isinstance(members, list):
            return {
                "status": "error",
                "message": "Members list is required and must be a valid JSON array"
            }
        
        if not notification_type:
            return {
                "status": "error",
                "message": "Notification type is required"
            }
        
        if not message_template:
            return {
                "status": "error",
                "message": "Message template is required"
            }
        
        # Send batch notifications
        result = send_batch_notifications(
            members=members,
            notification_type=notification_type,
            message_template=message_template,
            channel=channel,
            reference_document=reference_document,
            reference_name=reference_name
        )
        
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG API - Send Batch Notifications Error")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False)
def get_unread_notifications_count():
    """
    Get count of unread notifications for a member
    
    Required params:
    - member_id: ID of the member
    """
    try:
        member_id = frappe.form_dict.get('member_id')
        
        if not member_id:
            return {
                "status": "error",
                "message": "Member ID is required"
            }
        
        # Count notifications (for now, just count all since we don't have a read status field)
        # In a real implementation, you'd have a separate read receipts mechanism
        count = frappe.db.count("SHG Notification Log", {"member": member_id})
        
        return {
            "status": "success",
            "unread_count": count
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG API - Get Unread Notifications Count Error")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False)
def test_notification_connection():
    """
    Test if notification service is properly configured
    
    Required params:
    - channel: Channel to test (SMS, Email, WhatsApp)
    """
    try:
        channel = frappe.form_dict.get('channel', 'SMS')
        
        # Get SHG Settings to check if the channel is enabled
        settings = frappe.get_single("SHG Settings")
        
        if channel == "SMS":
            is_enabled = settings.sms_enabled
            provider = getattr(settings, 'sms_provider', 'Generic')
            return {
                "status": "success",
                "enabled": bool(is_enabled),
                "provider": provider,
                "channel": "SMS"
            }
        elif channel == "Email":
            is_enabled = settings.email_enabled
            return {
                "status": "success",
                "enabled": bool(is_enabled),
                "channel": "Email"
            }
        elif channel == "WhatsApp":
            # Check if WhatsApp business API is configured
            has_token = bool(getattr(settings, 'whatsapp_business_token', None))
            return {
                "status": "success",
                "enabled": has_token,
                "channel": "WhatsApp"
            }
        else:
            return {
                "status": "error",
                "message": f"Unsupported channel: {channel}"
            }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG API - Test Notification Connection Error")
        return {
            "status": "error",
            "message": str(e)
        }