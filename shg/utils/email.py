# Copyright (c) 2025, SHG Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, fmt_money, get_url_to_form
from frappe import _

def send_monthly_statement(member_name):
    """Send monthly statement to a member"""
    try:
        # Get member details
        member = frappe.get_doc("SHG Member", member_name)
        
        # Get SHG Settings
        settings = frappe.get_single("SHG Settings")
        
        # Check if email statements are enabled
        if not settings.enable_monthly_statements:
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
        
        # Prepare email content
        template = settings.statement_email_template or """Dear {member_name},

Please find your monthly statement for {month} {year}.

Total Contributions: {total_contributions}
Total Loan Repayments: {total_repayments}
Outstanding Loan Balance: {outstanding_balance}

Thank you for your continued support.

SHG Management"""
        
        email_content = template.format(
            member_name=member.member_name,
            month=month,
            year=year,
            total_contributions=total_contributions_formatted,
            total_repayments=total_repayments_formatted,
            outstanding_balance=outstanding_balance_formatted
        )
        
        # Send email
        if member.email:
            frappe.sendmail(
                recipients=[member.email],
                sender=settings.statement_sender_email,
                subject=settings.statement_email_subject or f"Monthly SHG Statement - {month} {year}",
                message=email_content
            )
            
            # Log the notification
            notification = frappe.get_doc({
                "doctype": "SHG Notification Log",
                "member": member_name,
                "notification_type": "Monthly Statement",
                "message": f"Monthly statement sent for {month} {year}",
                "channel": "Email",
                "status": "Sent",
                "sent_date": frappe.utils.now()
            })
            notification.insert()
            frappe.db.commit()
            
            return True
        else:
            frappe.log_error(f"Member {member_name} does not have an email address")
            return False
            
    except Exception as e:
        frappe.log_error(f"Failed to send monthly statement to {member_name}: {str(e)}")
        return False

def send_monthly_statements():
    """Send monthly statements to all active members"""
    try:
        # Get SHG Settings
        settings = frappe.get_single("SHG Settings")
        
        # Check if email statements are enabled
        if not settings.enable_monthly_statements:
            return
            
        # Get all active members with email addresses
        members = frappe.get_all("SHG Member",
                               filters={
                                   "membership_status": "Active",
                                   "email": ["!=", ""]
                               },
                               fields=["name", "member_name", "email"])
        
        success_count = 0
        failure_count = 0
        
        for member in members:
            if send_monthly_statement(member.name):
                success_count += 1
            else:
                failure_count += 1
                
        frappe.msgprint(_(f"Monthly statements sent: {success_count} successful, {failure_count} failed"))
        
    except Exception as e:
        frappe.log_error(f"Failed to send monthly statements: {str(e)}")
        frappe.msgprint(_("Failed to send monthly statements. Please check the error log."))