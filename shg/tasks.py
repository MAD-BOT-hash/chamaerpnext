import frappe
from frappe.utils import today, add_days, getdate
from datetime import datetime, timedelta

def all():
    """Task that runs every few minutes"""
    pass

def hourly():
    """Task that runs every hour"""
    pass

def send_daily_reminders():
    """Send daily reminders for upcoming due dates"""
    # Send loan reminders for loans due in 3 days
    upcoming_due_date = add_days(today(), 3)
    
    upcoming_loans = frappe.get_all("SHG Loan", 
                                   filters={
                                       "status": "Disbursed",
                                       "next_due_date": upcoming_due_date
                                   },
                                   fields=["name", "member", "member_name", "monthly_installment"])
    
    for loan in upcoming_loans:
        send_loan_reminder(loan.name)
        
    # Send overdue reminders
    overdue_loans = get_overdue_loans()
    for loan in overdue_loans:
        overdue_days = (getdate(today()) - getdate(loan.next_due_date)).days
        if overdue_days % 7 == 0:  # Send weekly reminders for overdue
            send_overdue_reminder(loan.name)
            
    # Send bi-monthly contribution reminders
    send_bimonthly_contribution_reminders()

def calculate_loan_penalties():
    """Calculate and apply penalties for overdue loans"""
    overdue_loans = get_overdue_loans()
    
    for loan in overdue_loans:
        # Calculate penalty (e.g., 5% of installment per month overdue)
        overdue_days = (getdate(today()) - getdate(loan.next_due_date)).days
        penalty_rate = 0.05  # 5%
        penalty_months = overdue_days / 30
        penalty_amount = loan.monthly_installment * penalty_rate * penalty_months
        
        # Check if penalty already applied today
        existing_penalty = frappe.db.exists("SHG Loan Penalty", {
            "loan": loan.name,
            "penalty_date": today()
        })
        
        if not existing_penalty and penalty_amount > 0:
            try:
                penalty_entry = frappe.get_doc({
                    "doctype": "SHG Loan Penalty",
                    "loan": loan.name,
                    "member": loan.member,
                    "penalty_date": today(),
                    "overdue_days": overdue_days,
                    "penalty_amount": penalty_amount,
                    "reason": f"Overdue payment - {overdue_days} days"
                })
                penalty_entry.insert()
                frappe.db.commit()
            except Exception as e:
                frappe.log_error(f"Failed to create penalty for loan {loan.name}: {str(e)}")

def send_weekly_contribution_reminders():
    """Send weekly contribution reminders"""
    # Get all active members
    active_members = frappe.get_all("SHG Member",
                                   filters={"membership_status": "Active"},
                                   fields=["name", "member_name", "phone_number"])
    
    # Get SHG Settings for contribution amount
    try:
        settings = frappe.get_single("SHG Settings")
        contribution_amount = settings.default_contribution_amount or 500
    except:
        contribution_amount = 500
    
    for member in active_members:
        # Check if member has contributed this week
        week_start = add_days(today(), -7)
        recent_contribution = frappe.db.exists("SHG Contribution", {
            "member": member.name,
            "contribution_date": ["between", [week_start, today()]]
        })
        
        if not recent_contribution:
            send_contribution_reminder(member.name, contribution_amount)

def send_bimonthly_contribution_reminders():
    """Send bi-monthly contribution reminders"""
    # Get all active members
    active_members = frappe.get_all("SHG Member",
                                   filters={"membership_status": "Active"},
                                   fields=["name", "member_name", "phone_number"])
    
    # Get bi-monthly contribution types
    bimonthly_types = frappe.get_all("SHG Contribution Type",
                                    filters={"frequency": "Bi-Monthly", "enabled": 1},
                                    fields=["name", "default_amount"])
    
    for contrib_type in bimonthly_types:
        for member in active_members:
            # Check if member has contributed for this bi-monthly type recently
            fortnight_start = add_days(today(), -15)  # Approximately half a month
            recent_contribution = frappe.db.exists("SHG Contribution", {
                "member": member.name,
                "contribution_type_link": contrib_type.name,
                "contribution_date": ["between", [fortnight_start, today()]]
            })
            
            if not recent_contribution:
                send_bimonthly_contribution_reminder(member.name, contrib_type.name, contrib_type.default_amount)

def generate_monthly_reports():
    """Generate monthly reports"""
    try:
        # Generate financial summary report
        # This would typically involve creating a report document or sending notifications
        frappe.log("Monthly reports generation completed")
    except Exception as e:
        frappe.log_error(f"Failed to generate monthly reports: {str(e)}")

def get_overdue_loans():
    """Get list of overdue loans"""
    return frappe.db.sql("""
        SELECT 
            l.name,
            l.member,
            m.member_name,
            m.phone_number,
            l.loan_amount,
            l.balance_amount,
            l.monthly_installment,
            l.next_due_date,
            DATEDIFF(%s, l.next_due_date) as overdue_days
        FROM `tabSHG Loan` l
        JOIN `tabSHG Member` m ON l.member = m.name
        WHERE l.status = 'Disbursed' 
        AND l.next_due_date < %s
        AND l.balance_amount > 0
        ORDER BY overdue_days DESC
    """, (today(), today()), as_dict=True)

def send_loan_reminder(loan_name):
    """Send loan repayment reminder"""
    try:
        loan = frappe.get_doc("SHG Loan", loan_name)
        member = frappe.get_doc("SHG Member", loan.member)
        
        message = f"Dear {member.member_name}, your loan repayment of KES {loan.monthly_installment:,.2f} is due on {loan.next_due_date}."
        
        # Create notification log
        notification = frappe.get_doc({
            "doctype": "SHG Notification Log",
            "member": loan.member,
            "notification_type": "Loan Reminder",
            "message": message,
            "channel": "SMS",
            "reference_document": "SHG Loan",
            "reference_name": loan_name
        })
        notification.insert()
        
        # Send SMS (implement based on your SMS provider)
        send_sms(member.phone_number, message)
        
        notification.status = "Sent"
        notification.sent_date = frappe.utils.now()
        notification.save()
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Failed to send loan reminder: {str(e)}")

def send_overdue_reminder(loan_name):
    """Send overdue loan reminder"""
    try:
        loan = frappe.get_doc("SHG Loan", loan_name)
        member = frappe.get_doc("SHG Member", loan.member)
        
        overdue_days = (getdate(today()) - getdate(loan.next_due_date)).days
        
        message = f"URGENT: Dear {member.member_name}, your loan is {overdue_days} days overdue. Amount: KES {loan.monthly_installment:,.2f}"
        
        notification = frappe.get_doc({
            "doctype": "SHG Notification Log", 
            "member": loan.member,
            "notification_type": "Overdue Reminder",
            "message": message,
            "channel": "SMS",
            "reference_document": "SHG Loan",
            "reference_name": loan_name
        })
        notification.insert()
        
        send_sms(member.phone_number, message)
        
        notification.status = "Sent"
        notification.sent_date = frappe.utils.now()
        notification.save()
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Failed to send overdue reminder: {str(e)}")

def send_contribution_reminder(member_name, amount):
    """Send contribution reminder"""
    try:
        member = frappe.get_doc("SHG Member", member_name)
        
        message = f"Dear {member.member_name}, your weekly contribution of KES {amount:,.2f} is due."
        
        notification = frappe.get_doc({
            "doctype": "SHG Notification Log",
            "member": member_name,
            "notification_type": "Contribution Reminder", 
            "message": message,
            "channel": "SMS"
        })
        notification.insert()
        
        send_sms(member.phone_number, message)
        
        notification.status = "Sent"
        notification.sent_date = frappe.utils.now() 
        notification.save()
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Failed to send contribution reminder: {str(e)}")

def send_bimonthly_contribution_reminder(member_name, contrib_type_name, amount):
    """Send bi-monthly contribution reminder"""
    try:
        member = frappe.get_doc("SHG Member", member_name)
        contrib_type = frappe.get_doc("SHG Contribution Type", contrib_type_name)
        
        message = f"Dear {member.member_name}, your {contrib_type.contribution_type_name} of KES {amount:,.2f} is due."
        
        notification = frappe.get_doc({
            "doctype": "SHG Notification Log",
            "member": member_name,
            "notification_type": "Contribution Reminder", 
            "message": message,
            "channel": "SMS"
        })
        notification.insert()
        
        send_sms(member.phone_number, message)
        
        notification.status = "Sent"
        notification.sent_date = frappe.utils.now() 
        notification.save()
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Failed to send bi-monthly contribution reminder: {str(e)}")

def send_sms(phone_number, message):
    """Send SMS using configured SMS gateway"""
    try:
        settings = frappe.get_single("SHG Settings")
        
        if not hasattr(settings, 'sms_api_key') or not settings.sms_api_key:
            frappe.log_error("SMS settings not configured")
            return False
            
        # Example integration with Africa's Talking
        import requests
        
        url = "https://api.africastalking.com/version1/messaging"
        headers = {
            "apiKey": settings.sms_api_key,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "username": getattr(settings, 'sms_username', 'sandbox'),
            "to": phone_number,
            "message": message,
            "from": getattr(settings, 'sms_sender_id', 'SHG')
        }
        
        response = requests.post(url, headers=headers, data=data)
        
        if response.status_code == 201:
            return True
        else:
            frappe.log_error(f"SMS sending failed with status code: {response.status_code}")
            return False
    except Exception as e:
        frappe.log_error(f"Failed to send SMS: {str(e)}")
        return False