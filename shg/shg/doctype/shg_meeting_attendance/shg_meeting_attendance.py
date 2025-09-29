import frappe
from frappe.model.document import Document
from frappe.utils import get_time

class SHGMeetingAttendance(Document):
    def validate(self):
        """Validate attendance record"""
        self.calculate_fine_amount()
        
    def calculate_fine_amount(self):
        """Calculate fine based on attendance status and arrival time"""
        # Reset fine amount
        self.fine_amount = 0
        
        # Get settings
        try:
            settings = frappe.get_single("SHG Settings")
            absentee_fine = settings.absentee_fine or 0
            lateness_fine = settings.lateness_fine or 0
        except Exception:
            # Fallback defaults
            absentee_fine = 50
            lateness_fine = 20
            
        # Apply fines based on attendance status
        if self.attendance_status == "Absent":
            self.fine_amount = absentee_fine
        elif self.attendance_status == "Late":
            self.fine_amount = lateness_fine
        # For "Present", no fine is applied