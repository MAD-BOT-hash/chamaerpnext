import frappe
import json

def safe_log_error(title: str, data=None):
    """Truncate title to 120 chars and log data in message"""
    short_title = (title[:120] + '...') if len(title) > 120 else title
    msg = json.dumps(data, indent=2, default=str) if data else ""
    frappe.log_error(title=short_title, message=msg)