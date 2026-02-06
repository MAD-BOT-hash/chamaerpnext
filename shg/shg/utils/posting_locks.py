import frappe
from frappe.utils import getdate, today
from datetime import datetime

def validate_posting_date(posting_date):
    """
    Validate that the posting date is not in a locked period
    
    Args:
        posting_date: The date to validate
        
    Raises:
        frappe.ValidationError: If the posting date is in a locked period
    """
    # Get SHG Settings
    shg_settings = frappe.get_single("SHG Settings")
    
    if not shg_settings.enable_posting_lock:
        return  # Skip validation if posting lock is disabled
    
    posting_date_obj = getdate(posting_date)
    
    # Check if date is before the global lock date
    if shg_settings.posting_locked_until:
        locked_until_date = getdate(shg_settings.posting_locked_until)
        if posting_date_obj <= locked_until_date:
            frappe.throw(
                f"Posting date {posting_date} is before the locked date {locked_until_date}. "
                f"{shg_settings.posting_lock_message}"
            )
    
    # Check if the specific month/year is locked
    year = posting_date_obj.year
    month = posting_date_obj.strftime("%B")  # Full month name like "January"
    
    if shg_settings.locked_months:
        for locked_month in shg_settings.locked_months:
            if locked_month.month == month and locked_month.year == year and locked_month.status == "Locked":
                frappe.throw(
                    f"The month of {month} {year} is locked for posting. "
                    f"{shg_settings.posting_lock_message}"
                )

def is_posting_date_locked(posting_date):
    """
    Check if a posting date is locked without throwing an exception
    
    Args:
        posting_date: The date to check
        
    Returns:
        bool: True if the date is locked, False otherwise
    """
    try:
        validate_posting_date(posting_date)
        return False
    except frappe.ValidationError:
        return True

def get_locked_months():
    """
    Get a list of currently locked months
    
    Returns:
        list: List of locked months in format "Month Year"
    """
    shg_settings = frappe.get_single("SHG Settings")
    locked_months = []
    
    if shg_settings.locked_months:
        for locked_month in shg_settings.locked_months:
            if locked_month.status == "Locked":
                locked_months.append(f"{locked_month.month} {locked_month.year}")
    
    return locked_months

def lock_month(month, year):
    """
    Lock a specific month for posting
    
    Args:
        month: Month name (e.g., "January")
        year: Year (e.g., 2024)
    """
    shg_settings = frappe.get_single("SHG Settings")
    
    # Check if the month/year combination already exists
    month_exists = False
    for locked_month in shg_settings.locked_months:
        if locked_month.month == month and locked_month.year == year:
            locked_month.status = "Locked"
            month_exists = True
            break
    
    # If it doesn't exist, add it
    if not month_exists:
        shg_settings.append("locked_months", {
            "month": month,
            "year": year,
            "status": "Locked"
        })
    
    shg_settings.save()

def unlock_month(month, year):
    """
    Unlock a specific month for posting
    
    Args:
        month: Month name (e.g., "January")
        year: Year (e.g., 2024)
    """
    shg_settings = frappe.get_single("SHG Settings")
    
    # Set the status to unlocked for the specified month/year
    for locked_month in shg_settings.locked_months:
        if locked_month.month == month and locked_month.year == year:
            locked_month.status = "Unlocked"
    
    shg_settings.save()