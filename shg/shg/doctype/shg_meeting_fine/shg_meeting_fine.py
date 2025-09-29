import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, getdate

class SHGMeetingFine(Document):
    def validate(self):
        self.validate_amount()
        self.validate_duplicate()
        
    def validate_amount(self):
        """Validate fine amount"""
        if self.fine_amount <= 0:
            frappe.throw(_("Fine amount must be greater than zero"))
            
    def validate_duplicate(self):
        """Check for duplicate fines"""
        existing = frappe.db.exists("SHG Meeting Fine", {
            "member": self.member,
            "meeting": self.meeting,
            "fine_reason": self.fine_reason,
            "docstatus": 1,
            "name": ["!=", self.name]
        })
        if existing:
            frappe.throw(_("A fine already exists for this member for the same reason"))
            
    def on_submit(self):
        if self.status == "Paid":
            self.post_to_general_ledger()
            
    def on_update(self):
        """Update status when paid date is set"""
        if self.paid_date and self.status != "Paid":
            self.status = "Paid"
            self.save()
            
    def post_to_general_ledger(self):
        """Post fine to General Ledger using Journal Entry"""
        if self.journal_entry:
            return
            
        company = frappe.defaults.get_user_default("Company")
        if not company:
            companies = frappe.get_all("Company", limit=1)
            if companies:
                company = companies[0].name
            else:
                frappe.throw(_("Please create a company first"))
                
        # Get member's account
        member_account = self.get_member_account()
        if not member_account:
            frappe.throw(_("Member account not found"))
            
        # Get fine income account
        fine_account = frappe.db.get_value("Account", 
            {"account_name": "SHG Penalty Income", "company": company})
        if not fine_account:
            frappe.throw(_("SHG Penalty Income account not found"))
            
        # Create Journal Entry
        je = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "posting_date": self.fine_date,
            "company": company,
            "remark": f"Meeting fine from {self.member_name} - {self.fine_reason}",
            "accounts": [
                {
                    "account": member_account,
                    "debit_in_account_currency": self.fine_amount,
                    "party_type": "Customer",
                    "party": self.get_member_customer(),
                    "reference_type": "SHG Meeting Fine",
                    "reference_name": self.name
                },
                {
                    "account": fine_account,
                    "credit_in_account_currency": self.fine_amount,
                    "reference_type": "SHG Meeting Fine",
                    "reference_name": self.name
                }
            ]
        })
        
        je.insert()
        je.submit()
        
        # Update fine record
        self.journal_entry = je.name
        self.save()
        
        # Send notification to member
        self.send_fine_notification()
        
    def get_member_account(self):
        """Get member's ledger account"""
        member = frappe.get_doc("SHG Member", self.member)
        company = frappe.defaults.get_user_default("Company")
        if not company:
            companies = frappe.get_all("Company", limit=1)
            if companies:
                company = companies[0].name
                
        account_name = f"{member.member_name} - SHG Members - {company}"
        return frappe.db.get_value("Account", {"name": account_name})
        
    def get_member_customer(self):
        """Get member's customer link"""
        member = frappe.get_doc("SHG Member", self.member)
        return member.customer_link
        
    def send_fine_notification(self):
        """Send fine notification to member"""
        member = frappe.get_doc("SHG Member", self.member)
        
        message = f"Dear {member.member_name}, a fine of KES {self.fine_amount:,.2f} has been applied for {self.fine_reason.lower()}."
        
        notification = frappe.get_doc({
            "doctype": "SHG Notification Log",
            "member": self.member,
            "notification_type": "Meeting Fine",
            "message": message,
            "channel": "SMS",
            "reference_document": "SHG Meeting Fine",
            "reference_name": self.name
        })
        notification.insert()
        
        # Send SMS (would be implemented in actual system)
        # send_sms(member.phone_number, message)