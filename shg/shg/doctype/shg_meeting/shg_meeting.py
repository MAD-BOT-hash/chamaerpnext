import frappe
from frappe.model.document import Document
from frappe.utils import today, getdate, flt

# Import the utility functions
from shg.shg.utils.meeting_utils import get_fine_reason_from_attendance, sanitize_fine_reason

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
        self.auto_invoice_absent_members()
        
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
            
            # Use the mapping to get the correct fine reason
            mapped_fine_reason = get_fine_reason_from_attendance(row.attendance_status)
            mapped_fine_reason = sanitize_fine_reason(mapped_fine_reason)
            
            if row.attendance_status == "Absent" and absentee_fine > 0:
                fine_amount = absentee_fine
                fine_reason = mapped_fine_reason
                
            elif row.attendance_status == "Late" and lateness_fine > 0:
                fine_amount = lateness_fine
                fine_reason = mapped_fine_reason
                
            if fine_amount > 0 and fine_reason:
                try:
                    # Create fine using the utility function
                    from shg.shg.utils.meeting_utils import create_meeting_fine
                    fine_entry = create_meeting_fine(
                        member=row.member,
                        attendance_status=row.attendance_status,
                        meeting_date=self.meeting_date,
                        meeting_name=self.name,
                        amount=fine_amount
                    )
                    frappe.logger().debug(f"Created fine entry {fine_entry.name} with reason '{fine_reason}' for member {row.member}")
                except Exception as e:
                    frappe.log_error(f"Failed to create fine entry for {row.member}: {str(e)}")
                    
    def auto_invoice_absent_members(self):
        """Generate invoices for absent members when meeting is submitted"""
        try:
            # Check if auto invoicing is enabled
            settings = frappe.get_single("SHG Settings")
            if not settings.auto_invoice_absentees:
                return
                
            # Validate required settings
            if not settings.absent_fee or settings.absent_fee <= 0:
                frappe.log("Auto-invoicing skipped: absent fee not configured")
                return
                
            if not settings.invoice_item:
                frappe.log("Auto-invoicing skipped: invoice item not configured")
                return
                
            absent_members = [row for row in self.attendance if row.attendance_status == "Absent"]
            if not absent_members:
                return
                
            generated_invoices = []
            for row in absent_members:
                invoice = self.create_absentee_invoice(row.member, settings)
                if invoice:
                    generated_invoices.append(invoice)
                    
            if generated_invoices:
                frappe.log(f"Generated {len(generated_invoices)} invoices for absent members in meeting {self.name}")
                
        except Exception as e:
            frappe.log_error(f"Failed to auto-invoice absent members for meeting {self.name}: {str(e)}")
            
    def create_absentee_invoice(self, member, settings):
        """Create a sales invoice for an absent member"""
        try:
            # Get member details
            member_doc = frappe.get_doc("SHG Member", member)
            if not member_doc.customer:
                frappe.log(f"Skipped invoicing for member {member_doc.name} - no customer record")
                return None
                
            # Create sales invoice
            invoice = frappe.get_doc({
                "doctype": "Sales Invoice",
                "customer": member_doc.customer,
                "posting_date": self.meeting_date,
                "due_date": self.meeting_date,
                "items": [{
                    "item_code": settings.invoice_item,
                    "item_name": frappe.get_value("Item", settings.invoice_item, "item_name"),
                    "description": f"Absence fine for meeting on {self.meeting_date}",
                    "qty": 1,
                    "rate": settings.absent_fee,
                    "amount": settings.absent_fee,
                    "cost_center": settings.cost_center,
                    "income_account": settings.income_account
                }],
                "remarks": f"Absence fine for meeting on {self.meeting_date}",
                "shg_meeting": self.name
            })
            
            invoice.insert()
            invoice.submit()
            
            # Send email notification
            self.send_absentee_invoice_email(member_doc, invoice, settings)
            
            return invoice
            
        except Exception as e:
            frappe.log_error(f"Failed to create invoice for absent member {member}: {str(e)}")
            return None
            
    def send_absentee_invoice_email(self, member_doc, invoice, settings):
        """Send email notification to absent member with invoice attachment"""
        try:
            if not member_doc.email:
                frappe.log(f"Member {member_doc.name} has no email address")
                return False
                
            # Prepare email content
            subject = f"Absence Fine for Meeting on {self.meeting_date}"
            
            message = f"""Dear {member_doc.member_name},

You were marked absent for the SHG meeting held on {self.meeting_date}.
A fine of KES {settings.absent_fee:,.2f} has been invoiced to your account.

Please find your invoice attached.

Regards,
SHG Management"""
            
            # Send email with invoice attachment
            frappe.sendmail(
                recipients=[member_doc.email],
                subject=subject,
                message=message,
                attachments=[frappe.attach_print("Sales Invoice", invoice.name, file_name=invoice.name)]
            )
            
            return True
            
        except Exception as e:
            frappe.log_error(f"Failed to send invoice email to member {member_doc.name}: {str(e)}")
            return False
                    
    @frappe.whitelist()
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

# This is a hook function called from hooks.py and should NOT have @frappe.whitelist()
def process_attendance_fines(doc, method):
    """Hook function called from hooks.py"""
    doc.process_attendance_fines()