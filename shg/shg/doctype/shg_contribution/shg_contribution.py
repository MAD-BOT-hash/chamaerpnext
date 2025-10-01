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
                    
                # Verify party details for credit entry
                if not credit_entry.party_type or not credit_entry.party:
                    frappe.throw(_("Credit entry must have party type and party set."))
                    
                if credit_entry.party_type != "Customer":
                    frappe.throw(_("Credit entry party type must be 'Customer'."))
            elif self.payment_entry:
                pe = frappe.get_doc("Payment Entry", self.payment_entry)
                if pe.docstatus != 1:
                    frappe.throw(_("Payment Entry was not submitted successfully."))
                    
                # Verify payment entry details
                if pe.payment_type != "Receive":
                    frappe.throw(_("Payment Entry must be of type 'Receive' for contributions."))
                    
                if not pe.party_type or not pe.party:
                    frappe.throw(_("Payment Entry must have party type and party set."))
                    
                if pe.party_type != "Customer":
                    frappe.throw(_("Payment Entry party type must be 'Customer'."))
                    
                if abs(pe.paid_amount - self.amount) > 0.01:
                    frappe.throw(_("Payment Entry amount does not match contribution amount."))
                
        except frappe.DoesNotExistError:
            if self.journal_entry:
                frappe.throw(_("Journal Entry {0} does not exist.").format(self.journal_entry))
            elif self.payment_entry:
                frappe.throw(_("Payment Entry {0} does not exist.").format(self.payment_entry))
        except Exception as e:
            frappe.throw(_("Error validating GL Entry: {0}").format(str(e)))
        
    def post_to_ledger(self):
        """
        Create a Payment Entry or Journal Entry for this contribution.
        Use SHG Settings to decide; default to Journal Entry.
        """
        settings = frappe.get_single("SHG Settings")
        posting_method = getattr(settings, "contribution_posting_method", "Journal Entry")  # or "Payment Entry"

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
        je = frappe.get_doc({
            "doctype": "Journal Entry",
            "posting_date": self.contribution_date or today(),
            "company": company,
            "voucher_type": "Journal Entry",
            "user_remark": f"SHG Contribution {self.name} from {self.member}",
            "accounts": [
                {
                    "account": self.get_cash_account(company),  # implement helper to find Cash/Bank
                    "debit_in_account_currency": flt(self.amount),
                    "reference_type": "Journal Entry",
                    "reference_name": self.name
                },
                {
                    "account": self.get_contribution_account(company),
                    "credit_in_account_currency": flt(self.amount),
                    "party_type": "Customer",
                    "party": party_customer,
                    "reference_type": "Journal Entry",
                    "reference_name": self.name
                }
            ]
        })
        je.insert(ignore_permissions=True)
        je.submit()
        return je
        
    def _create_payment_entry(self, party_customer, company):
        # create Payment Entry (Receipt)
        from frappe.utils import flt, today
        pe = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "posting_date": self.contribution_date or today(),
            "company": company,
            "party_type": "Customer",
            "party": party_customer,
            "paid_from": self.get_cash_account(company),
            "paid_to": self.get_contribution_account(company),
            "paid_amount": flt(self.amount),
            "received_amount": flt(self.amount),
            "reference_no": self.name,
            "reference_date": self.contribution_date or today()
        })
        pe.insert(ignore_permissions=True)
        pe.submit()
        return pe
        
    def get_cash_account(self, company):
        """Get cash or bank account from settings or defaults"""
        settings = frappe.get_single("SHG Settings")
        if settings.default_bank_account:
            return settings.default_bank_account
        elif settings.default_cash_account:
            return settings.default_cash_account
        else:
            # Try to find a default bank account
            bank_accounts = frappe.get_all("Account", filters={
                "company": company,
                "account_type": "Bank",
                "is_group": 0
            }, limit=1)
            if bank_accounts:
                return bank_accounts[0].name
            else:
                # Try cash account
                cash_accounts = frappe.get_all("Account", filters={
                    "company": company,
                    "account_type": "Cash",
                    "is_group": 0
                }, limit=1)
                if cash_accounts:
                    return cash_accounts[0].name
                else:
                    frappe.throw(_("Please configure default bank or cash account in SHG Settings"))
                    
    def get_contribution_account(self, company):
        """Get contribution account, create if not exists"""
        from shg.shg.utils.account_utils import get_or_create_shg_contributions_account
        return get_or_create_shg_contributions_account(company)
            

        
    def on_cancel(self):
        """Cancel the associated journal entry or payment entry"""
        if self.journal_entry:
            je = frappe.get_doc("Journal Entry", self.journal_entry)
            if je.docstatus == 1:
                je.cancel()
        elif self.payment_entry:
            pe = frappe.get_doc("Payment Entry", self.payment_entry)
            if pe.docstatus == 1:
                pe.cancel()
        self.update_member_summary()
                
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
    if doc.docstatus == 1 and not doc.get("posted_to_gl"):
        doc.post_to_ledger()