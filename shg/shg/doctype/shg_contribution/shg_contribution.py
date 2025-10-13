import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, getdate, formatdate, add_days

class SHGContribution(Document):
    def validate(self):
        self.validate_amount()
        self.validate_duplicate()
        self.set_contribution_details()
        self.calculate_unpaid_amount()
        
        # Ensure amount is rounded to 2 decimal places
        if self.amount:
            self.amount = round(float(self.amount), 2)
        if self.expected_amount:
            self.expected_amount = round(float(self.expected_amount), 2)
        if self.amount_paid:
            self.amount_paid = round(float(self.amount_paid), 2)
        if self.unpaid_amount:
            self.unpaid_amount = round(float(self.unpaid_amount), 2)
        
    def validate_amount(self):
        """Validate contribution amount"""
        if self.amount <= 0:
            frappe.throw(_("Contribution amount must be greater than zero"))
            
    def validate_duplicate(self):
        """Check for duplicate contributions on same date"""
        existing = frappe.db.exists("SHG Contribution", {
            "member": self.member,
            "contribution_date": self.contribution_date,
            "docstatus": 1,
            "name": ["!=", self.name]
        })
        if existing:
            frappe.throw(_("A contribution already exists for this member on this date"))
            
    def set_contribution_details(self):
        """Set contribution details from contribution type"""
        if self.contribution_type_link:
            contrib_type = frappe.get_doc("SHG Contribution Type", self.contribution_type_link)
            if not self.expected_amount and contrib_type.default_amount:
                self.expected_amount = contrib_type.default_amount
        elif self.contribution_type:
            # Get from settings
            settings = frappe.get_doc("SHG Settings")
            if not self.expected_amount:
                if self.contribution_type == "Regular Weekly":
                    self.expected_amount = settings.default_contribution_amount
                elif self.contribution_type == "Regular Monthly":
                    self.expected_amount = settings.default_contribution_amount * 4  # Approximate
                elif self.contribution_type == "Bi-Monthly":
                    self.expected_amount = settings.default_contribution_amount * 8  # Approximate
                    
        # If expected_amount is set but amount_paid is not, initialize amount_paid to 0
        if self.expected_amount and not self.amount_paid:
            self.amount_paid = 0
            
    def calculate_unpaid_amount(self):
        """Calculate unpaid amount and set status"""
        # If expected_amount is not set, use the amount field as expected_amount
        if not self.expected_amount:
            self.expected_amount = self.amount
            
        # If amount_paid is not set, initialize it to 0
        if not self.amount_paid:
            self.amount_paid = 0
            
        # Calculate unpaid amount
        self.unpaid_amount = max(0, self.expected_amount - self.amount_paid)
        
        # Set status based on unpaid amount
        if self.unpaid_amount <= 0:
            self.status = "Paid"
        elif self.amount_paid > 0:
            self.status = "Partially Paid"
        else:
            self.status = "Unpaid"
            
    def on_submit(self):
        # ensure idempotent: if already posted -> skip
        if not self.get("posted_to_gl"):
            self.post_to_ledger()
        self.update_member_summary()
        
    def on_cancel(self):
        self.cancel_journal_entry()
        self.update_member_summary()
        
    def validate_gl_entries(self):
        """Validate that GL entries were created properly"""
        if not self.journal_entry and not self.payment_entry:
            frappe.throw(_("Failed to create Journal Entry or Payment Entry for this contribution. Please check the system logs."))
            
        # Use validation utilities
        from shg.shg.utils.validation_utils import validate_reference_types_and_names, validate_custom_field_linking, validate_accounting_integrity
        validate_reference_types_and_names(self)
        validate_custom_field_linking(self)
        validate_accounting_integrity(self)
        
    def post_to_ledger(self):
        """
        Create a Journal Entry for this contribution.
        """
        from shg.shg.utils.gl_utils import create_contribution_journal_entry, update_document_with_journal_entry
        journal_entry = create_contribution_journal_entry(self)
        update_document_with_journal_entry(self, journal_entry)
        
    def cancel_journal_entry(self):
        """Cancel the associated journal entry or payment entry"""
        if self.journal_entry:
            je = frappe.get_doc("Journal Entry", self.journal_entry)
            if je.docstatus == 1:
                je.cancel()
        elif self.payment_entry:
            pe = frappe.get_doc("Payment Entry", self.payment_entry)
            if pe.docstatus == 1:
                pe.cancel()
                
    def get_member_account(self):
        """Get member's ledger account, create if not exists"""
        member = frappe.get_doc("SHG Member", self.member)
        company = frappe.defaults.get_user_default("Company")
        if not company:
            companies = frappe.get_all("Company", limit=1)
            if companies:
                company = companies[0].name
            else:
                frappe.throw(_("Please create a company first"))
                
        from shg.shg.utils.account_utils import get_or_create_member_account
        return get_or_create_member_account(member, company)
        
    def get_member_customer(self):
        """Get member's customer link"""
        member = frappe.get_doc("SHG Member", self.member)
        return member.customer
        
    def update_member_summary(self):
        """Update member's financial summary"""
        member = frappe.get_doc("SHG Member", self.member)
        member.update_financial_summary()
        
    @frappe.whitelist()
    def get_suggested_amount(self):
        """Get suggested contribution amount based on type and member"""
        if self.contribution_type_link:
            contrib_type = frappe.get_doc("SHG Contribution Type", self.contribution_type_link)
            return contrib_type.default_amount
        elif self.contribution_type:
            # Get from settings
            settings = frappe.get_doc("SHG Settings")
            if self.contribution_type == "Regular Weekly":
                return settings.default_contribution_amount
            elif self.contribution_type == "Regular Monthly":
                return settings.default_contribution_amount * 4  # Approximate
            elif self.contribution_type == "Bi-Monthly":
                return settings.default_contribution_amount * 8  # Approximate
        return 0
        
    @frappe.whitelist()
    def send_payment_confirmation(self):
        """Send payment confirmation SMS"""
        member = frappe.get_doc("SHG Member", self.member)
        
        message = f"Dear {member.member_name}, your contribution of KES {self.amount:,.2f} has been received. Thank you for your continued support."
        
        # Log notification
        notification = frappe.get_doc({
            "doctype": "SHG Notification Log",
            "member": self.member,
            "notification_type": "Payment Confirmation",
            "message": message,
            "channel": "SMS",
            "reference_document": "SHG Contribution",
            "reference_name": self.name
        })
        notification.insert()
        
        # In a real implementation, you would send the actual SMS
        # send_sms(member.phone_number, message)
        return True
        
    @frappe.whitelist()
    def initiate_mpesa_stk_push(self):
        """Initiate Mpesa STK Push for contribution payment"""
        try:
            # Check if Mpesa is enabled
            settings = frappe.get_doc("SHG Settings")
            if not settings.mpesa_enabled:
                return {"success": False, "error": "Mpesa payments are not enabled"}
                
            member = frappe.get_doc("SHG Member", self.member)
            
            # In a real implementation, you would integrate with Mpesa API
            # This is a placeholder for the actual implementation
            # mpesa_response = make_mpesa_stk_push_request(
            #     phone_number=member.phone_number,
            #     amount=self.amount,
            #     account_reference=self.name,
            #     transaction_desc=f"SHG Contribution - {self.member_name}"
            # )
            
            # For now, return a success response
            return {"success": True, "message": "Mpesa STK Push initiated successfully"}
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Contribution - Mpesa STK Push Failed")
            return {"success": False, "error": str(e)}

@frappe.whitelist()
def generate_contribution_invoices(invoice_date, amount, contribution_type=None, remarks=None, send_email=0):
    active_members = frappe.get_all("SHG Member", filters={"membership_status": "Active"}, fields=["name", "member_name", "email"])
    created = 0

    for m in active_members:
        # Calculate due date (30 days from invoice date)
        due_date = frappe.utils.add_days(invoice_date, 30)
        
        inv = frappe.get_doc({
            "doctype": "SHG Contribution Invoice",
            "member": m.name,
            "member_name": m.member_name,
            "invoice_date": invoice_date,
            "due_date": due_date,
            "amount": amount,
            "contribution_type": contribution_type,
            "status": "Unpaid",
            "description": remarks or f"Contribution invoice for {formatdate(invoice_date, 'MMMM yyyy')}"
        })
        inv.insert(ignore_permissions=True)
        inv.submit()
        created += 1

    frappe.msgprint(_("{0} contribution invoices created successfully.").format(created))
    return created

@frappe.whitelist()
def send_contribution_invoice_emails(invoice_date):
    """Send emails for all contribution invoices created on the given date"""
    # Get all contribution invoices created on the given date
    invoices = frappe.get_all("SHG Contribution Invoice", 
                             filters={
                                 "invoice_date": invoice_date,
                                 "status": "Unpaid",
                                 "docstatus": 1
                             },
                             fields=["name"])
    
    sent = 0
    for invoice in invoices:
        try:
            inv_doc = frappe.get_doc("SHG Contribution Invoice", invoice.name)
            inv_doc.send_invoice_email()
            sent += 1
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to send email for invoice {invoice.name}")
    
    frappe.msgprint(_("{0} invoice emails sent successfully.").format(sent))
    return sent

# --- Hook functions ---
# These are hook functions called from hooks.py and should NOT have @frappe.whitelist()
def validate_contribution(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()

def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    if doc.docstatus == 1 and not doc.get("posted_to_gl"):
        doc.post_to_ledger()

def update_overdue_contributions():
    """Scheduled job to update overdue contributions"""
    # Get all unpaid contributions where due date has passed
    overdue_contributions = frappe.db.sql("""
        SELECT name
        FROM `tabSHG Contribution`
        WHERE docstatus = 1 
        AND status = 'Unpaid'
        AND contribution_date < %s
    """, getdate(), as_dict=True)
    
    updated_count = 0
    for contrib in overdue_contributions:
        try:
            contribution = frappe.get_doc("SHG Contribution", contrib.name)
            # Send reminder email
            send_contribution_reminder(contribution)
            updated_count += 1
        except Exception as e:
            frappe.log_error(f"Failed to process overdue contribution {contrib.name}: {str(e)}")
    
    frappe.msgprint(f"Processed {updated_count} overdue contributions")

def send_contribution_reminder(contribution):
    """Send email reminder for unpaid contribution"""
    try:
        member = frappe.get_doc("SHG Member", contribution.member)
        if member.email:
            # Create email content
            subject = "Unpaid Contribution Reminder"
            message = f"""
            <p>Dear {member.member_name},</p>
            <p>This is a reminder that you have an unpaid contribution of KES {contribution.unpaid_amount:,.2f} 
            due on {formatdate(contribution.contribution_date)}.</p>
            <p>Please make the payment at your earliest convenience.</p>
            <p>Thank you for your continued support.</p>
            """
            
            # Send email
            frappe.sendmail(
                recipients=[member.email],
                subject=subject,
                message=message
            )
            
            frappe.msgprint(f"Reminder email sent to {member.member_name}")
    except Exception as e:
        frappe.log_error(f"Failed to send reminder for contribution {contribution.name}: {str(e)}")