import frappe
from frappe.model.document import Document
from frappe.utils import today, getdate, flt

class SHGMeeting(Document):
    def validate(self):
        """Validate meeting data"""
        self.validate_meeting_date()
        self.calculate_attendance_summary()
        
    def validate_meeting_date(self):
        """Validate meeting date"""
        if self.meeting_date and getdate(self.meeting_date) < getdate(today()):
            frappe.msgprint("Meeting date is in the past", alert=True)
            
    def calculate_attendance_summary(self):
        """Calculate attendance statistics"""
        if not self.attendance:
            return
        
        total_members = len(self.attendance)
        present_members = len([a for a in self.attendance if a.attendance_status == "Present"])
        late_members = len([a for a in self.attendance if a.attendance_status == "Late"])
        absent_members = len([a for a in self.attendance if a.attendance_status == "Absent"])
        
        self.total_members = total_members
        self.members_present = present_members
        self.members_late = late_members
        self.members_absent = absent_members
        
        self.attendance_percentage = (
            ((present_members + late_members) / total_members) * 100 if total_members > 0 else 0
        )
            
    def on_submit(self):
        """Process attendance and apply fines"""
        self.process_attendance_fines()
        
    def process_attendance_fines(self):
        """Apply fines for absentees and late comers"""
        if not self.attendance:
            return
            
        try:
            settings = frappe.get_single("SHG Settings")
            absentee_fine = settings.absentee_fine or 0
            lateness_fine = settings.lateness_fine or 0
        except Exception:
            absentee_fine = 50  # Fallback default
            lateness_fine = 20
            
        for row in self.attendance:
            fine_amount = 0
            fine_reason = ""
            
            if row.attendance_status == "Absent" and absentee_fine > 0:
                fine_amount = absentee_fine
                fine_reason = f"Absentee fine for meeting on {self.meeting_date}"
                
            elif row.attendance_status == "Late" and lateness_fine > 0:
                fine_amount = lateness_fine
                fine_reason = f"Lateness fine for meeting on {self.meeting_date}"
                
            if fine_amount > 0:
                try:
                    fine_entry = frappe.get_doc({
                        "doctype": "SHG Meeting Fine",  # Ensure this DocType exists
                        "member": row.member,
                        "meeting": self.name,
                        "fine_amount": fine_amount,
                        "fine_reason": fine_reason,
                        "fine_date": today()
                    })
                    fine_entry.insert(ignore_permissions=True)
                except Exception as e:
                    frappe.log_error(f"Failed to create fine entry for {row.member}: {str(e)}")
                    
    def get_member_list(self):
        """Get all active members for attendance"""
        active_members = frappe.get_all(
            "SHG Member", 
            filters={"membership_status": "Active"},
            fields=["name", "member_name", "phone_number"]
        )
        
        return [
            {
                "member": m.name,
                "member_name": m.member_name,
                "attendance_status": "Present"  # Default
            }
            for m in active_members
        ]

def process_attendance_fines(doc, method):
    """Hook function called from hooks.py"""
    doc.process_attendance_fines()
