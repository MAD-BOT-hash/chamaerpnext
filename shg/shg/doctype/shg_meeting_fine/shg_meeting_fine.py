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
            # ensure idempotent: if already posted -> skip
            if not self.get("posted_to_gl"):
                self.post_to_ledger()
            self.validate_gl_entries()
            
    def on_update(self):
        """Update status when paid date is set"""
        if self.paid_date and self.status != "Paid":
            self.status = "Paid"
            self.save()
            
    def validate_gl_entries(self):
        """Validate that GL entries were created properly"""
        if not self.journal_entry and not self.payment_entry:
            frappe.throw(_("Failed to create Journal Entry or Payment Entry for this meeting fine. Please check the system logs."))
            
        # Verify the journal entry or payment entry exists and is submitted
        try:
            if self.journal_entry:
                je = frappe.get_doc("Journal Entry", self.journal_entry)
                if je.docstatus != 1:
                    frappe.throw(_("Journal Entry was not submitted successfully."))
                    
                # Verify accounts and amounts
                if len(je.accounts) != 2:
                    frappe.throw(_("Journal Entry should have exactly 2 accounts."))
                    
                debit_entry = None
                credit_entry = None
                
                for entry in je.accounts:
                    if entry.debit_in_account_currency > 0:
                        debit_entry = entry
                    elif entry.credit_in_account_currency > 0:
                        credit_entry = entry
                        
                if not debit_entry or not credit_entry:
                    frappe.throw(_("Journal Entry must have one debit and one credit entry."))
                    
                if abs(debit_entry.debit_in_account_currency - credit_entry.credit_in_account_currency) > 0.01:
                    frappe.throw(_("Debit and credit amounts must be equal."))
                    
                # Verify party details for debit entry
                if not debit_entry.party_type or not debit_entry.party:
                    frappe.throw(_("Debit entry must have party type and party set."))
                    
                if debit_entry.party_type != "Customer":
                    frappe.throw(_("Debit entry party type must be 'Customer'."))
                    
                # Verify custom field linking
                if not je.custom_shg_meeting_fine or je.custom_shg_meeting_fine != self.name:
                    frappe.throw(_("Journal Entry must be linked to this SHG Meeting Fine."))
            elif self.payment_entry:
                pe = frappe.get_doc("Payment Entry", self.payment_entry)
                if pe.docstatus != 1:
                    frappe.throw(_("Payment Entry was not submitted successfully."))
                    
                # Verify payment entry details
                if pe.payment_type != "Receive":
                    frappe.throw(_("Payment Entry must be of type 'Receive' for meeting fines."))
                    
                if not pe.party_type or not pe.party:
                    frappe.throw(_("Payment Entry must have party type and party set."))
                    
                if pe.party_type != "Customer":
                    frappe.throw(_("Payment Entry party type must be 'Customer'."))
                    
                if abs(pe.paid_amount - self.fine_amount) > 0.01:
                    frappe.throw(_("Payment Entry amount does not match fine amount."))
                    
                # Verify custom field linking
                if not pe.custom_shg_meeting_fine or pe.custom_shg_meeting_fine != self.name:
                    frappe.throw(_("Payment Entry must be linked to this SHG Meeting Fine."))
        except frappe.DoesNotExistError:
            if self.journal_entry:
                frappe.throw(_("Journal Entry {0} does not exist.").format(self.journal_entry))
            elif self.payment_entry:
                frappe.throw(_("Payment Entry {0} does not exist.").format(self.payment_entry))
        except Exception as e:
            frappe.throw(_("Error validating GL Entry: {0}").format(str(e)))
            
    def post_to_ledger(self):
        """
        Create a Payment Entry or Journal Entry for this meeting fine.
        Use SHG Settings to decide; default to Journal Entry.
        """
        settings = frappe.get_single("SHG Settings")
        # For meeting fines, we'll default to Journal Entry as they're typically internal adjustments
        posting_method = getattr(settings, "meeting_fine_posting_method", "Journal Entry")

        # Prepare common data
        company = frappe.get_value("Global Defaults", None, "default_company") or settings.company
        member_customer = frappe.get_value("SHG Member", self.member, "customer")

        # Choose posting
        if posting_method == "Payment Entry":
            pe = self._create_payment_entry(member_customer, company)
            self.payment_entry = pe.name
        else:
            je = self._create_journal_entry(member_customer, company)
            self.journal_entry = je.name

        self.posted_to_gl = 1
        self.posted_on = frappe.utils.now()
        self.save()
        
    def _create_journal_entry(self, party_customer, company):
        from frappe.utils import flt, today
        
        # Get member's account
        member_account = self.get_member_account()
        if not member_account:
            frappe.throw(_("Member account not found"))
            
        # Get fine income account using the new utility function
        from shg.shg.utils.account_utils import get_or_create_shg_penalty_income_account
        fine_account = get_or_create_shg_penalty_income_account(company)
            
        # Create Journal Entry
        je = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "posting_date": self.fine_date or today(),
            "company": company,
            "remark": f"SHG Meeting Fine {self.name} from {self.member_name} - {self.fine_reason}",
            "custom_shg_meeting_fine": self.name,
            "accounts": [
                {
                    "account": member_account,
                    "debit_in_account_currency": flt(self.fine_amount),
                    "party_type": "Customer",
                    "party": party_customer
                },
                {
                    "account": fine_account,
                    "credit_in_account_currency": flt(self.fine_amount)
                }
            ]
        })
        
        je.insert(ignore_permissions=True)
        je.submit()
        
        # Send notification to member
        self.send_fine_notification()
        
        return je
        
    def _create_payment_entry(self, party_customer, company):
        # create Payment Entry (Receive - the member pays the fine)
        from frappe.utils import flt, today
        pe = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "posting_date": self.fine_date or today(),
            "company": company,
            "party_type": "Customer",
            "party": party_customer,
            "paid_from": self.get_member_account(),
            "paid_to": self.get_fine_account(company),
            "paid_amount": flt(self.fine_amount),
            "received_amount": flt(self.fine_amount),
            "reference_no": self.name,
            "reference_date": self.fine_date or today(),
            "custom_shg_meeting_fine": self.name
        })
        pe.insert(ignore_permissions=True)
        pe.submit()
        
        # Send notification to member
        self.send_fine_notification()
        
        return pe
        
    def get_fine_account(self, company):
        """Get fine income account, create if not exists"""
        from shg.shg.utils.account_utils import get_or_create_shg_penalty_income_account
        return get_or_create_shg_penalty_income_account(company)
        
    def get_member_account(self):
        """Get member's ledger account"""
        member = frappe.get_doc("SHG Member", self.member)
        company = frappe.defaults.get_user_default("Company")
        if not company:
            companies = frappe.get_all("Company", limit=1)
            if companies:
                company = companies[0].name
                
        from shg.shg.utils.account_utils import get_or_create_member_account
        return get_or_create_member_account(member, company)
        
    def get_member_customer(self):
        """Get member's customer link"""
        member = frappe.get_doc("SHG Member", self.member)
        return member.customer
        
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