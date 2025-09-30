# Copyright (c) 2025, SHG Solutions and contributors
# For license information, please see license.txt

import frappe
import requests
from frappe.utils import getdate, fmt_money

def send_whatsapp_message(phone_number, message):
    """Send WhatsApp message using Twilio or Frappe WhatsApp connector"""
    try:
        # Get SHG Settings
        settings = frappe.get_single("SHG Settings")
        
        # Check if WhatsApp is enabled
        if not settings.sms_enabled:  # Using sms_enabled as WhatsApp enabled flag
            frappe.log_error("WhatsApp notifications are not enabled in SHG Settings")
            return False
            
        # Try to use Frappe WhatsApp if available
        if frappe.get_installed_apps().get("frappe_whatsapp"):
            return send_via_frappe_whatsapp(phone_number, message)
        else:
            # Fall back to Twilio
            return send_via_twilio(phone_number, message)
            
    except Exception as e:
        frappe.log_error(f"Failed to send WhatsApp message: {str(e)}")
        return False

def send_via_frappe_whatsapp(phone_number, message):
    """Send WhatsApp message using Frappe WhatsApp connector"""
    try:
        # Create WhatsApp message
        whatsapp_message = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "to": phone_number,
            "message": message,
            "message_type": "text"
        })
        whatsapp_message.insert(ignore_permissions=True)
        
        # Send the message
        whatsapp_message.send()
        
        return True
    except Exception as e:
        frappe.log_error(f"Failed to send WhatsApp via Frappe WhatsApp: {str(e)}")
        return False

def send_via_twilio(phone_number, message):
    """Send WhatsApp message using Twilio API"""
    try:
        # Get Twilio settings from SHG Settings
        settings = frappe.get_single("SHG Settings")
        
        # Check if we have Twilio credentials
        if not hasattr(settings, 'sms_api_key') or not settings.sms_api_key:
            frappe.log_error("Twilio API key not configured")
            return False
            
        # Format phone number for Twilio (E.164 format)
        formatted_phone = format_phone_for_twilio(phone_number)
        
        # Twilio API credentials
        account_sid = settings.sms_api_key
        auth_token = settings.sms_secret if hasattr(settings, 'sms_secret') else ""
        from_number = settings.sms_sender_id if hasattr(settings, 'sms_sender_id') else ""
        
        # Twilio WhatsApp API endpoint
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        
        # Message payload
        data = {
            "From": f"whatsapp:{from_number}",
            "To": f"whatsapp:{formatted_phone}",
            "Body": message
        }
        
        # Send request
        response = requests.post(url, data=data, auth=(account_sid, auth_token))
        
        if response.status_code == 201:
            return True
        else:
            frappe.log_error(f"Twilio WhatsApp API error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        frappe.log_error(f"Failed to send WhatsApp via Twilio: {str(e)}")
        return False

def format_phone_for_twilio(phone_number):
    """Format phone number for Twilio (E.164 format)"""
    # Remove any non-digit characters
    clean_number = ''.join(filter(str.isdigit, phone_number))
    
    # Handle Kenyan phone numbers
    if clean_number.startswith('0'):
        # Convert 07xx or 01xx to +254
        clean_number = '254' + clean_number[1:]
    elif clean_number.startswith('254'):
        # Already in correct format
        pass
    elif clean_number.startswith('+254'):
        # Remove the +
        clean_number = clean_number[1:]
    else:
        # Assume it's already in international format without +
        pass
        
    return '+' + clean_number

def send_monthly_statement_whatsapp(member_name):
    """Send monthly statement via WhatsApp to a member"""
    try:
        # Get member details
        member = frappe.get_doc("SHG Member", member_name)
        
        # Get SHG Settings
        settings = frappe.get_single("SHG Settings")
        
        # Check if notifications are enabled
        if not settings.sms_enabled:  # Using sms_enabled as WhatsApp enabled flag
            return False
            
        # Get current month and year
        from frappe.utils import nowdate
        current_date = getdate(nowdate())
        month = current_date.strftime("%B")
        year = current_date.year
        
        # Get member's contributions for the month
        contributions = frappe.get_all("SHG Contribution",
                                     filters={
                                         "member": member_name,
                                         "contribution_date": ["like", f"{year}-{current_date.month:02d}%"],
                                         "docstatus": 1
                                     },
                                     fields=["contribution_type_link", "amount"])
        
        total_contributions = sum([c.amount for c in contributions])
        
        # Get member's loan repayments for the month
        repayments = frappe.get_all("SHG Loan Repayment",
                                  filters={
                                      "member": member_name,
                                      "repayment_date": ["like", f"{year}-{current_date.month:02d}%"],
                                      "docstatus": 1
                                  },
                                  fields=["amount"])
        
        total_repayments = sum([r.amount for r in repayments])
        
        # Get member's current loan balance
        member_doc = frappe.get_doc("SHG Member", member_name)
        outstanding_balance = member_doc.current_loan_balance or 0
        
        # Format currency values
        currency = settings.currency or "KES"
        total_contributions_formatted = fmt_money(total_contributions, currency=currency)
        total_repayments_formatted = fmt_money(total_repayments, currency=currency)
        outstanding_balance_formatted = fmt_money(outstanding_balance, currency=currency)
        
        # Prepare WhatsApp message
        message = f"""*Monthly SHG Statement - {month} {year}*

Member: {member.member_name}

Total Contributions: {total_contributions_formatted}
Total Loan Repayments: {total_repayments_formatted}
Outstanding Loan Balance: {outstanding_balance_formatted}

Thank you for your continued support.
SHG Management"""
        
        # Send WhatsApp message
        if member.phone_number:
            if send_whatsapp_message(member.phone_number, message):
                # Log the notification
                notification = frappe.get_doc({
                    "doctype": "SHG Notification Log",
                    "member": member_name,
                    "notification_type": "Monthly Statement",
                    "message": f"Monthly statement sent via WhatsApp for {month} {year}",
                    "channel": "WhatsApp",
                    "status": "Sent",
                    "sent_date": frappe.utils.now()
                })
                notification.insert()
                frappe.db.commit()
                
                return True
            else:
                return False
        else:
            frappe.log_error(f"Member {member_name} does not have a phone number")
            return False
            
    except Exception as e:
        frappe.log_error(f"Failed to send monthly statement via WhatsApp to {member_name}: {str(e)}")
        return False

def send_monthly_statements_whatsapp():
    """Send monthly statements via WhatsApp to all active members"""
    try:
        # Get SHG Settings
        settings = frappe.get_single("SHG Settings")
        
        # Check if WhatsApp notifications are enabled
        if not settings.sms_enabled:  # Using sms_enabled as WhatsApp enabled flag
            return
            
        # Get all active members with phone numbers
        members = frappe.get_all("SHG Member",
                               filters={
                                   "membership_status": "Active",
                                   "phone_number": ["!=", ""]
                               },
                               fields=["name", "member_name", "phone_number"])
        
        success_count = 0
        failure_count = 0
        
        for member in members:
            if send_monthly_statement_whatsapp(member.name):
                success_count += 1
            else:
                failure_count += 1
                
        frappe.msgprint(f"Monthly WhatsApp statements sent: {success_count} successful, {failure_count} failed")
        
    except Exception as e:
        frappe.log_error(f"Failed to send monthly WhatsApp statements: {str(e)}")
        frappe.msgprint("Failed to send monthly WhatsApp statements. Please check the error log.")