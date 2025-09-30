# Copyright (c) 2025, SHG Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

class SHGMemberAttendance(Document):
    def validate(self):
        self.calculate_attendance_summary()
        
    def before_submit(self):
        self.calculate_attendance_summary()
        
    def calculate_attendance_summary(self):
        """Calculate attendance summary from the attendance table"""
        present = 0
        absent = 0
        late = 0
        excused = 0
        
        for row in self.attendance:
            if row.attendance_status == "Present":
                present += 1
            elif row.attendance_status == "Absent":
                absent += 1
            elif row.attendance_status == "Late":
                late += 1
            elif row.attendance_status == "Excused":
                excused += 1
                
        self.members_present = present
        self.members_absent = absent
        self.members_late = late
        self.members_excused = excused
        self.total_members = present + absent + late + excused
        
        if self.total_members > 0:
            self.attendance_percentage = (present + late + excused) / self.total_members * 100
        else:
            self.attendance_percentage = 0
            
    @frappe.whitelist()
    def populate_attendance(self):
        """Populate attendance table with all active members"""
        # Clear existing attendance records
        self.attendance = []
        
        # Get all active members
        members = frappe.get_all("SHG Member", 
                                filters={"membership_status": "Active"},
                                fields=["name", "member_name"])
        
        # Add each member to attendance table
        for member in members:
            self.append("attendance", {
                "member": member.name,
                "member_name": member.member_name,
                "attendance_status": "Present"
            })
            
        # Update summary
        self.total_members = len(members)
        self.members_present = len(members)
        self.members_absent = 0
        self.members_late = 0
        self.members_excused = 0
        self.attendance_percentage = 100.0 if len(members) > 0 else 0