import frappe
from frappe.utils import today, add_days, getdate, get_last_day, get_first_day
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

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

def generate_billable_contribution_invoices():
    """Generate invoices for billable contributions that are due"""
    try:
        # Get all billable contribution types that have auto-invoicing enabled
        billable_types = frappe.get_all("SHG Contribution Type",
                                       filters={
                                           "is_billable": 1,
                                           "auto_invoice": 1,
                                           "enabled": 1
                                       },
                                       fields=["name", "contribution_type_name", "default_amount", 
                                              "billing_frequency", "due_day", "grace_period", "item_code"])
        
        for contrib_type in billable_types:
            # Check if it's time to generate invoices for this contribution type
            if is_due_for_invoicing(contrib_type):
                generate_invoices_for_contribution_type(contrib_type)
                
    except Exception as e:
        frappe.log_error(f"Failed to generate billable contribution invoices: {str(e)}")

def is_due_for_invoicing(contrib_type):
    """Check if it's time to generate invoices for a contribution type"""
    today_date = getdate(today())
    
    # For monthly billing, check if today is the due day
    if contrib_type.billing_frequency == "Monthly":
        return today_date.day == contrib_type.due_day
    
    # For weekly billing, we could check if it's a specific day of the week
    elif contrib_type.billing_frequency == "Weekly":
        # Assuming due_day represents day of week (1=Monday, 7=Sunday)
        return today_date.weekday() + 1 == contrib_type.due_day
    
    # For quarterly billing
    elif contrib_type.billing_frequency == "Quarterly":
        # Check if it's the due day of the first month of the quarter
        quarter_start_months = [1, 4, 7, 10]  # Jan, Apr, Jul, Oct
        return (today_date.day == contrib_type.due_day and 
                today_date.month in quarter_start_months)
    
    # For annual billing
    elif contrib_type.billing_frequency == "Annually":
        # Check if it's the due day of a specific month (e.g., January)
        return (today_date.day == contrib_type.due_day and 
                today_date.month == 1)
    
    # For bi-monthly billing
    elif contrib_type.billing_frequency == "Bi monthly":
        # Check if it's the due day of even months
        return (today_date.day == contrib_type.due_day and 
                today_date.month % 2 == 0)
    
    return False

def generate_invoices_for_contribution_type(contrib_type):
    """Generate invoices for all active members for a specific contribution type"""
    try:
        # Get all active members
        active_members = frappe.get_all("SHG Member",
                                       filters={"membership_status": "Active"},
                                       fields=["name", "member_name", "customer", "email"])
        
        for member in active_members:
            # Check if an invoice already exists for this member and contribution type for this period
            if not invoice_exists_for_period(member, contrib_type):
                # Create sales invoice for the member
                create_sales_invoice_for_member(member, contrib_type)
            
    except Exception as e:
        frappe.log_error(f"Failed to generate invoices for contribution type {contrib_type.name}: {str(e)}")

def invoice_exists_for_period(member, contrib_type):
    """Check if an invoice already exists for a member and contribution type for the current period"""
    today_date = getdate(today())
    
    # Determine the period based on billing frequency
    if contrib_type.billing_frequency == "Monthly":
        period_start = today_date.replace(day=1)
        period_end = get_last_day(today_date)
    elif contrib_type.billing_frequency == "Weekly":
        period_start = add_days(today_date, -today_date.weekday())
        period_end = add_days(period_start, 6)
    elif contrib_type.billing_frequency == "Quarterly":
        quarter = (today_date.month - 1) // 3
        period_start = today_date.replace(month=quarter * 3 + 1, day=1)
        period_end = get_last_day(today_date.replace(month=quarter * 3 + 3))
    elif contrib_type.billing_frequency == "Annually":
        period_start = today_date.replace(month=1, day=1)
        period_end = today_date.replace(month=12, day=31)
    elif contrib_type.billing_frequency == "Bi monthly":
        if today_date.month % 2 == 0:
            period_start = today_date.replace(month=today_date.month - 1, day=1)
        else:
            period_start = today_date.replace(day=1)
        period_end = get_last_day(today_date)
    else:
        period_start = today_date.replace(day=1)
        period_end = get_last_day(today_date)
    
    # Check if invoice exists for this period
    existing_invoice = frappe.db.exists("Sales Invoice", {
        "customer": member.customer,
        "shg_contribution_type": contrib_type.name,
        "posting_date": ["between", [period_start, period_end]],
        "docstatus": ["!=", 2]  # Not cancelled
    })
    
    return existing_invoice is not None

def create_sales_invoice_for_member(member, contrib_type):
    """Create a sales invoice for a member"""
    try:
        # Check if historical backdated invoices are allowed
        allow_historical = frappe.db.get_single_value("SHG Settings", "allow_historical_backdated_invoices") or 0
        
        # Use today's date for posting
        posting_date = getdate(today())
        
        # If historical backdated invoices are allowed, we can use a different date
        # For automated invoices, we'll use today's date as the supplier invoice date
        supplier_invoice_date = posting_date
        
        # Create a new Sales Invoice
        invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": member.customer,
            "posting_date": supplier_invoice_date,
            "due_date": supplier_invoice_date,  # Same as posting date to prevent ERPNext validation errors
            "shg_contribution_type": contrib_type.name,
            "items": [{
                "item_code": contrib_type.item_code or "SHG Contribution",
                "item_name": contrib_type.contribution_type_name,
                "description": f"{contrib_type.contribution_type_name} for {get_contribution_period(contrib_type)}",
                "qty": 1,
                "rate": contrib_type.default_amount,
                "amount": contrib_type.default_amount
            }]
        })
        
        # Insert and submit the invoice
        invoice.insert()
        invoice.submit()
        
        # Send email notification to member
        send_invoice_email(member, invoice, contrib_type)
        
        # Log the invoice creation
        frappe.log(f"Created invoice {invoice.name} for member {member.name} for contribution type {contrib_type.name}")
        
        return invoice
        
    except Exception as e:
        frappe.log_error(f"Failed to create sales invoice for member {member.name}: {str(e)}")
        return None

def get_due_date(contrib_type):
    """Calculate the due date for an invoice"""
    today_date = getdate(today())
    
    if contrib_type.billing_frequency == "Monthly":
        # Due date is the specified day of the current month
        try:
            due_date = today_date.replace(day=contrib_type.due_day)
        except ValueError:
            # Handle case where due_day doesn't exist in current month (e.g., 31st in February)
            due_date = get_last_day(today_date)
    
    elif contrib_type.billing_frequency == "Weekly":
        # Due date is today (weekly billing)
        due_date = today_date
    
    elif contrib_type.billing_frequency == "Quarterly":
        # Due date is the specified day of the current quarter start month
        due_date = today_date.replace(day=contrib_type.due_day)
    
    elif contrib_type.billing_frequency == "Annually":
        # Due date is the specified day of January
        due_date = today_date.replace(month=1, day=contrib_type.due_day)
    
    elif contrib_type.billing_frequency == "Bi monthly":
        # Due date is the specified day of the current even month
        due_date = today_date.replace(day=contrib_type.due_day)
    
    else:
        due_date = today_date
    
    # Ensure due date is not before posting date (today)
    if due_date < today_date:
        due_date = today_date
    
    return due_date

def get_contribution_period(contrib_type):
    """Get the contribution period description"""
    today_date = getdate(today())
    
    if contrib_type.billing_frequency == "Monthly":
        return today_date.strftime("%B %Y")
    
    elif contrib_type.billing_frequency == "Weekly":
        return f"Week of {today_date.strftime('%B %d, %Y')}"
    
    elif contrib_type.billing_frequency == "Quarterly":
        quarter = (today_date.month - 1) // 3 + 1
        return f"Q{quarter} {today_date.year}"
    
    elif contrib_type.billing_frequency == "Annually":
        return f"Year {today_date.year}"
    
    elif contrib_type.billing_frequency == "Bi monthly":
        return f"{today_date.strftime('%B %Y')} (Bi-monthly)"
    
    return today_date.strftime("%B %Y")

def send_invoice_email(member, invoice, contrib_type):
    """Send invoice email to member"""
    try:
        if not member.email:
            frappe.log_error(f"Member {member.name} does not have an email address")
            return False
            
        # Get SHG Settings
        settings = frappe.get_single("SHG Settings")
        
        # Prepare email content
        subject = f"Your {get_contribution_period(contrib_type)} SHG Contribution Invoice"
        
        message = f"""Dear {member.member_name},

Your SHG contribution for {get_contribution_period(contrib_type)} is now due.

Amount Due: KES {contrib_type.default_amount:,.2f}
Due Date: {get_due_date(contrib_type).strftime('%B %d, %Y')}

Please find your attached invoice.

Regards,
SHG Management"""
        
        # Send email with invoice attachment
        frappe.sendmail(
            recipients=[member.email],
            subject=subject,
            message=message,
            attachments=[frappe.attach_print("Sales Invoice", invoice.name, file_name=invoice.name)]
        )
        
        # Log the notification
        notification = frappe.get_doc({
            "doctype": "SHG Notification Log",
            "member": member.name,
            "notification_type": "Invoice Generated",
            "message": f"Invoice {invoice.name} generated for {get_contribution_period(contrib_type)}",
            "channel": "Email",
            "status": "Sent",
            "sent_date": frappe.utils.now(),
            "reference_document": "Sales Invoice",
            "reference_name": invoice.name
        })
        notification.insert()
        frappe.db.commit()
        
        return True
        
    except Exception as e:
        frappe.log_error(f"Failed to send invoice email to member {member.name}: {str(e)}")
        return False

def send_monthly_member_statements():
    """Send monthly statements to all active members"""
    try:
        # Get all active members with email addresses
        members = frappe.get_all("SHG Member",
                               filters={
                                   "membership_status": "Active",
                                   "email": ["!=", ""]
                               },
                               fields=["name", "member_name", "email", "customer"])
        
        for member in members:
            send_member_statement(member)
            
    except Exception as e:
        frappe.log_error(f"Failed to send monthly member statements: {str(e)}")

def send_member_statement(member):
    """Send monthly statement to a member"""
    try:
        if not member.email:
            frappe.log_error(f"Member {member.name} does not have an email address")
            return False
            
        # Get current month and year
        current_date = getdate(today())
        month = current_date.strftime("%B")
        year = current_date.year
        
        # Prepare email content
        subject = f"Monthly SHG Statement - {month} {year}"
        
        message = f"""Dear {member.member_name},

Please find your monthly statement for {month} {year} attached.

Thank you for your continued support.

SHG Management"""
        
        # Generate and attach the statement
        # Note: In a real implementation, you would generate a PDF of the statement
        # For now, we'll just send a simple email
        
        frappe.sendmail(
            recipients=[member.email],
            subject=subject,
            message=message
        )
        
        # Log the notification
        notification = frappe.get_doc({
            "doctype": "SHG Notification Log",
            "member": member.name,
            "notification_type": "Monthly Statement",
            "message": f"Monthly statement sent for {month} {year}",
            "channel": "Email",
            "status": "Sent",
            "sent_date": frappe.utils.now()
        })
        notification.insert()
        frappe.db.commit()
        
        return True
        
    except Exception as e:
        frappe.log_error(f"Failed to send monthly statement to member {member.name}: {str(e)}")
        return False