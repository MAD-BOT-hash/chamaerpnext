import frappe

# Attendance to Fine Reason Mapping
ATTENDANCE_FINE_MAP = {
    "Absent": "Absentee",
    "Late": "Late Arrival",
    "No Uniform": "Uniform Violation",
    "Disruptive": "Noise Disturbance",
}

def get_fine_reason_from_attendance(status):
    """Get fine reason from attendance status"""
    return ATTENDANCE_FINE_MAP.get(status, "Other")