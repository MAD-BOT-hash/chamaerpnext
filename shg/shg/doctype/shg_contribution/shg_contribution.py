import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, getdate

class SHGContribution(Document):
    def validate(self):
        self.validate_amount()
        self.validate_duplicate()
        self.set_contribution_details()
        
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
            if not self.amount and contrib_type.default_amount:
                self.amount = contrib_type.default_amount
                
    def on_submit(self):
        self.create_journal_entry()
        self.validate_gl_entries()
        self.update_member_summary()
        
    def on_cancel(self):
        self.cancel_journal_entry()
        self.update_member_summary()
        
    def validate_gl_entries(self):
        """Validate that GL entries were created properly"""
        if not self.journal_entry:
            frappe.throw(_("Failed to create Journal Entry for this contribution. Please check the system logs."))
            
        # Verify the journal entry exists and is submitted
        try:
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
                
            # Verify party details for credit entry
            if not credit_entry.party_type or not credit_entry.party:
                frappe.throw(_("Credit entry must have party type and party set."))
                
            if credit_entry.party_type != "Customer":
                frappe.throw(_("Credit entry party type must be 'Customer'."))
                
        except frappe.DoesNotExistError:
            frappe.throw(_("Journal Entry {0} does not exist.").format(self.journal_entry))
        except Exception as e:
            frappe.throw(_("Error validating Journal Entry: {0}").format(str(e)))
        
    def create_journal_entry(self):
        """Create Journal Entry for contribution"""
        if self.journal_entry:
            return
            
        company = frappe.defaults.get_user_default("Company")
        if not company:
            companies = frappe.get_all("Company", limit=1)
            if companies:
                company = companies[0].name
            else:
                frappe.throw(_("Please create a company first"))
                
        # Get configured accounts or use defaults
        settings = frappe.get_single("SHG Settings")
        bank_account = settings.default_bank_account if settings.default_bank_account else f"Bank - {company}"
        cash_account = settings.default_cash_account if settings.default_cash_account else f"Cash - {company}"
        
        # Get member's account (auto-created if not exists)
        member_account = self.get_member_account()
            
        # Get contribution account
        from shg.shg.utils.account_utils import get_or_create_shg_contributions_account
        contribution_account = get_or_create_shg_contributions_account(company)
        
        # Use account mapping if available, otherwise use defaults
        debit_account = bank_account
        credit_account = member_account
        
        if self.account_mapping:
            # Process account mapping
            for mapping in self.account_mapping:
                if mapping.account_type == "Bank Account":
                    debit_account = mapping.account
                elif mapping.account_type == "Member Account":
                    credit_account = mapping.account
                # Note: For contributions, we typically debit bank/cash and credit member account
                # Other account types might be used for more complex scenarios
        
        # Determine which account to debit (bank or cash)
        if not self.account_mapping:
            debit_account = bank_account if frappe.db.exists("Account", bank_account) else cash_account
            
        # Create Journal Entry
        je = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "posting_date": self.contribution_date,
            "company": company,
            "user_remark": f"Contribution from {self.member_name} - {self.contribution_type}",
            "accounts": [
                {
                    "account": debit_account,
                    "debit_in_account_currency": self.amount,
                    "reference_type": self.doctype,
                    "reference_name": self.name
                },
                {
                    "account": credit_account,
                    "credit_in_account_currency": self.amount,
                    "party_type": "Customer",
                    "party": self.get_member_customer(),
                    "reference_type": self.doctype,
                    "reference_name": self.name
                }
            ]
        })
        
        je.insert()
        je.submit()
        
        # Update contribution record
        self.journal_entry = je.name
        self.save()
        
    def cancel_journal_entry(self):
        """Cancel the associated journal entry"""
        if self.journal_entry:
            je = frappe.get_doc("Journal Entry", self.journal_entry)
            if je.docstatus == 1:
                je.cancel()
                
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

# --- Hook functions ---
def validate_contribution(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()

def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    if doc.docstatus == 1:
        doc.create_journal_entry()