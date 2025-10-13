# shg/shg/utils/meeting_utils.py

import frappe

from frappe import _


ATTENDANCE_FINE_MAP = {
    "Absent": "Absentee",
    "Absent (Excused)": "Absentee",
    "Late": "Late Arrival",
    "Late Arrival": "Late Arrival",
    "No Uniform": "Uniform Violation",
    "Uniform Violation": "Uniform Violation",
    "Disruptive": "Noise Disturbance",
    "Noise Disturbance": "Noise Disturbance",
    # add other mappings as needed
}


ALLOWED_FINE_REASONS = [
    "Late Arrival",
    "Absentee",
    "Uniform Violation",
    "Noise Disturbance",
    "Other"
]


def get_fine_reason_from_attendance(attendance_status):
    """Map attendance status to allowed fine reason (short values)."""
    if not attendance_status:
        return "Other"
    reason = ATTENDANCE_FINE_MAP.get(attendance_status)
    if not reason:
        # fallback to 'Other' and log for investigation
        frappe.logger("shg").warning(
            f"Unmapped attendance status '{attendance_status}' — defaulting fine_reason to 'Other'"
        )
        return "Other"
    return reason


def sanitize_fine_reason(reason):
    """Ensure final fine_reason is one of allowed list (safety)."""
    if reason in ALLOWED_FINE_REASONS:
        return reason
    frappe.logger("shg").warning(f"Invalid fine reason '{reason}' encountered — using 'Other'")
    return "Other"


def create_meeting_fine(member, attendance_status, meeting_date, meeting_name, amount, created_by=None):
    """
    Create and return a SHG Meeting Fine doc for a member based on attendance_status.
    Keeps fine_reason short and stores verbose text in remarks to avoid 'Value too big' errors.
    """
    # Map attendance status to a short allowed fine reason
    fine_reason = get_fine_reason_from_attendance(attendance_status)
    fine_reason = sanitize_fine_reason(fine_reason)

    # Build a human-friendly remarks/title separately (this can be longer)
    remarks = f"{fine_reason} fine for meeting on {meeting_date}"
    # If you already produce a long message elsewhere, set it here:
    # remarks = f"Generated from attendance: {attendance_status} — {long_description_here}"

    # Create the fine document
    fine = frappe.get_doc({
        "doctype": "SHG Meeting Fine",
        "member": member,
        "meeting": meeting_name,
        "fine_date": meeting_date,
        "fine_amount": amount,
        "fine_reason": fine_reason,   # SHORT allowed value (select)
        "fine_description": remarks,  # LONG free-text field
        "created_by": created_by or frappe.session.user,
    })

    # Validate and insert (you may want ignore_permissions based on your flow)
    try:
        fine.insert(ignore_permissions=True)
        # if required, submit or submit later; depends on your doctype workflow
        return fine
    except Exception as e:
        frappe.log_error(f"Failed to create fine entry for {member}: {str(e)}", "SHG Meeting Fine Creation")
        raise