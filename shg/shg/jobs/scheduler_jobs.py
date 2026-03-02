"""
SHG Scheduler Jobs
Enterprise-grade background job definitions
"""
import frappe
from frappe import _
from shg.shg.services.services import get_service

def process_overdue_contributions():
    """Daily job to process overdue contributions"""
    try:
        scheduler_service = get_service('scheduler')
        result = scheduler_service.process_overdue_contributions()
        
        frappe.logger("scheduler").info(f"Overdue contributions processed: {result}")
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Overdue contributions processing failed")
        raise

def send_monthly_statements():
    """Monthly job to send member statements"""
    try:
        scheduler_service = get_service('scheduler')
        result = scheduler_service.process_monthly_statements()
        
        frappe.logger("scheduler").info(f"Monthly statements processed: {result}")
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Monthly statements processing failed")
        raise

def send_payment_reminders():
    """Daily job to send payment reminders"""
    try:
        scheduler_service = get_service('scheduler')
        result = scheduler_service.process_payment_reminders()
        
        frappe.logger("scheduler").info(f"Payment reminders processed: {result}")
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Payment reminders processing failed")
        raise

def update_member_summaries():
    """Daily job to update all member financial summaries"""
    try:
        member_service = get_service('member')
        
        # Get all active members
        active_members = frappe.get_all(
            "SHG Member",
            filters={"membership_status": "Active"},
            fields=["name"]
        )
        
        updated_count = 0
        failed_count = 0
        
        for member in active_members:
            try:
                member_service.update_member_financial_summary(member.name)
                updated_count += 1
            except Exception as e:
                frappe.logger("scheduler").error(f"Failed to update member {member.name}: {str(e)}")
                failed_count += 1
        
        result = {
            'total_members': len(active_members),
            'updated_count': updated_count,
            'failed_count': failed_count,
            'status': 'completed'
        }
        
        frappe.logger("scheduler").info(f"Member summaries updated: {result}")
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Member summaries update failed")
        raise

def process_auto_contributions():
    """Daily job to process auto-generated contributions"""
    try:
        # This would handle automatically generated contributions based on schedules
        # Implementation depends on your specific business rules
        pass
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Auto contributions processing failed")
        raise

def cleanup_old_logs():
    """Weekly job to clean up old log entries"""
    try:
        # Remove logs older than 90 days
        from frappe.utils import add_days
        cutoff_date = add_days(frappe.utils.today(), -90)
        
        log_types = [
            "SHG Contribution Log",
            "SHG Payment Log", 
            "SHG GL Log",
            "SHG Notification Log",
            "SHG Member Log",
            "SHG Scheduler Log"
        ]
        
        deleted_count = 0
        
        for log_type in log_types:
            try:
                old_logs = frappe.get_all(
                    log_type,
                    filters={"creation": ["<", cutoff_date]},
                    fields=["name"]
                )
                
                for log in old_logs:
                    frappe.delete_doc(log_type, log.name, ignore_permissions=True)
                    deleted_count += 1
                    
            except Exception as e:
                frappe.logger("scheduler").error(f"Failed to cleanup {log_type}: {str(e)}")
        
        result = {
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date,
            'status': 'completed'
        }
        
        frappe.logger("scheduler").info(f"Old logs cleaned up: {result}")
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Log cleanup failed")
        raise

# Job registration for Frappe scheduler
def get_scheduler_events():
    """Return scheduler events configuration"""
    return {
        "daily": [
            "shg.shg.jobs.scheduler_jobs.process_overdue_contributions",
            "shg.shg.jobs.scheduler_jobs.send_payment_reminders",
            "shg.shg.jobs.scheduler_jobs.update_member_summaries"
        ],
        "weekly": [
            "shg.shg.jobs.scheduler_jobs.cleanup_old_logs"
        ],
        "monthly": [
            "shg.shg.jobs.scheduler_jobs.send_monthly_statements",
            "shg.shg.jobs.scheduler_jobs.process_auto_contributions"
        ]
    }