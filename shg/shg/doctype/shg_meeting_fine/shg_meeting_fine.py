import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, getdate, flt, nowdate

class SHGMeetingFine(Document):
    """
    SHG Meeting Fine DocType.
    Provides ERPNext-compatible properties for Payment Entry integration.
    """
    
    # ========================================================================
    # ERPNext Payment Entry Compatibility Properties
    # ========================================================================
    
    @property
    def grand_total(self):
        """ERPNext compatibility - returns fine_amount or amount."""
        return flt(self.fine_amount or self.amount or 0)
    
    @property
    def base_grand_total(self):
        """ERPNext compatibility - returns fine_amount or amount."""
        return flt(self.fine_amount or self.amount or 0)
    
    @property
    def rounded_total(self):
        """ERPNext compatibility - returns fine_amount or amount."""
        return flt(self.fine_amount or self.amount or 0)
    
    @property
    def posting_date(self):
        """ERPNext compatibility - returns posting_date field or falls back to fine_date."""
        pd = getattr(self, '_posting_date', None) or self.get('posting_date')
        if pd:
            return pd
        return getattr(self, 'fine_date', None) or getattr(self, 'meeting_date', None) or today()
    
    @property
    def outstanding_amount(self):
        """ERPNext compatibility - calculates outstanding."""
        total = flt(self.fine_amount or self.amount or 0)
        paid = flt(getattr(self, 'paid_amount', 0) or 0)
        return total - paid
    
    @property
    def currency(self):
        """ERPNext compatibility - returns company currency."""
        if hasattr(self, 'company') and self.company:
            return frappe.db.get_value("Company", self.company, "default_currency") or "KES"
        return "KES"
    
    @property
    def conversion_rate(self):
        """ERPNext compatibility - returns 1.0."""
        return 1.0
    
    @property
    def advance_paid(self):
        """ERPNext compatibility - returns 0."""
        return 0.0
    
    @property
    def is_return(self):
        """ERPNext compatibility - returns False."""
        return False
    
    @property
    def customer(self):
        """ERPNext compatibility - returns member's customer."""
        if hasattr(self, 'member') and self.member:
            customer = frappe.db.get_value("SHG Member", self.member, "customer")
            return customer or self.member
        return None
    
    # ========================================================================
    # End ERPNext Compatibility Properties
    # ========================================================================
    
    def __getattr__(self, name):
        """Fallback for ERPNext attributes not explicitly defined."""
        common_financial_attrs = {
            "total_advance": 0.0, "base_total": 0.0, "net_total": 0.0,
            "base_net_total": 0.0, "total_taxes_and_charges": 0.0,
            "base_total_taxes_and_charges": 0.0, "discount_amount": 0.0,
            "base_discount_amount": 0.0, "write_off_amount": 0.0,
            "base_write_off_amount": 0.0, "rounding_adjustment": 0.0,
            "base_rounding_adjustment": 0.0, "paid_amount": 0.0,
            "base_paid_amount": 0.0, "change_amount": 0.0,
            "base_change_amount": 0.0, "loyalty_amount": 0.0,
            "in_words": "", "base_in_words": "", "total_qty": 1.0,
            "is_internal_customer": 0, "is_internal_supplier": 0,
            "group_same_items": 0, "disable_rounded_total": 0,
            "apply_discount_on": "", "additional_discount_percentage": 0.0,
        }
        if name in common_financial_attrs:
            return common_financial_attrs[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def validate(self):
        self.validate_fine_reason()
        self.validate_amount()
        self.validate_duplicate()
        self.autogenerate_description()
        
        # Ensure fine_amount is rounded to 2 decimal places
        if self.fine_amount:
            self.fine_amount = round(float(self.fine_amount), 2)
        
    def before_validate(self):
        """Ensure company is populated from SHG Settings."""
        try:
            from shg.shg.utils.company_utils import get_default_company
            if not getattr(self, "company", None):
                default_company = get_default_company()
                if default_company:
                    self.company = default_company
                else:
                    frappe.throw("Please set Default Company in SHG Settings before continuing.")
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"SHG Meeting Fine - Failed to set default company for {self.name}")
            frappe.throw(_(f"Failed to set default company: {str(e)}"))

    def validate_fine_reason(self):
        """Validate that fine_reason is one of the allowed options"""
        allowed_reasons = ["Late Arrival", "Absentee", "Uniform Violation", "Noise Disturbance", "Other"]
        if self.fine_reason and self.fine_reason not in allowed_reasons:
            frappe.throw(_("Invalid Fine Reason. Must be one of: {0}").format(", ".join(allowed_reasons)))
            
    def autogenerate_description(self):
        """Auto-generate fine description if not provided"""
        if not self.fine_description and self.fine_reason and self.meeting:
            try:
                # Safely get meeting date with fallback
                meeting_date = frappe.db.get_value("SHG Meeting", self.meeting, "meeting_date") or today()
                self.fine_description = f"{self.fine_reason} fine for meeting on {meeting_date}"
            except Exception as e:
                # Fallback to today's date if meeting date cannot be retrieved
                frappe.log_error(frappe.get_traceback(), f"SHG Meeting Fine - Failed to get meeting date for {self.meeting}")
                self.fine_description = f"{self.fine_reason} fine (date unavailable)"
        
    def validate_amount(self):
        """Validate fine amount"""
        if self.fine_amount <= 0:
            frappe.throw(_("Fine amount must be greater than zero"))
            
    def validate_duplicate(self):
        """Check for duplicate fines - consider only docstatus < 2 and exclude self"""
        try:
            existing = frappe.db.exists("SHG Meeting Fine", {
                "member": self.member,
                "meeting": self.meeting,
                "fine_reason": self.fine_reason,
                "docstatus": ["<", 2],  # Only check submitted and draft documents
                "name": ["!=", self.name]
            })
            if existing:
                frappe.throw(_("A fine already exists for this member for the same reason in meeting {0}".format(self.meeting)))
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"SHG Meeting Fine - Failed to validate duplicates for {self.name}")
            # Allow future meeting amendments by not throwing error in case of validation issues
            
    def on_submit(self):
        """Only post to ledger when status is 'Paid'"""
        if self.status == "Paid":
            # ensure idempotent: if already posted -> skip
            if not self.get("posted_to_gl"):
                self.post_to_ledger()
            self.validate_gl_entries()
        elif self.status == "Pending":
            frappe.msgprint(_("Fine is pending payment. Use 'Mark as Paid' to post to ledger."))
            
    def on_update(self):
        """Update status when paid date is set"""
        if self.paid_date and self.status != "Paid":
            self.status = "Paid"
            self.save()
            
    def validate_gl_entries(self):
        """Validate that GL entries were created properly"""
        try:
            if not self.journal_entry and not self.payment_entry:
                frappe.throw(_("Failed to create Journal Entry or Payment Entry for this meeting fine. Please check the system logs."))
                
            # Use validation utilities
            from shg.shg.utils.validation_utils import validate_reference_types_and_names, validate_custom_field_linking, validate_accounting_integrity
            validate_reference_types_and_names(self)
            validate_custom_field_linking(self)
            validate_accounting_integrity(self)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"SHG Meeting Fine - Failed to validate GL entries for {self.name}")
            frappe.throw(_(f"Failed to validate GL entries: {str(e)}"))
            
    def post_to_ledger(self):
        """
        Create a Journal Entry for this meeting fine.
        """
        try:
            # Add company source fallback
            if not self.company:
                settings_company = frappe.db.get_single_value("SHG Settings", "default_company")
                if not settings_company:
                    frappe.throw("Default Company is missing in SHG Settings.")
                self.company = settings_company

            # Use the new account helper
            from shg.shg.utils.account_utils import get_account
            member_account = get_account(self.company, "fines", self.member)
            
            # Get customer for the member with fallback
            customer = frappe.db.get_value("SHG Member", self.member, "customer")
            if not customer:
                # Fallback to member ID if no customer is linked
                customer = self.member
            
            # Get fine income account
            income_account = get_account(self.company, "fines")
            
            # Create journal entry with proper accounts
            je = frappe.new_doc("Journal Entry")
            je.voucher_type = "Journal Entry"
            je.company = self.company
            je.posting_date = self.paid_date or today()
            je.remark = f"Meeting fine from {self.member} for {self.fine_reason}"
            # Link back to SHG Meeting Fine using custom field
            je.custom_shg_meeting_fine = self.name

            # Debit: member receivable
            je.append("accounts", {
                "account": member_account,
                "party_type": "Customer",
                "party": customer,
                "debit_in_account_currency": self.fine_amount,
                "credit_in_account_currency": 0,
                "company": self.company
            })

            # Credit: fines income account
            je.append("accounts", {
                "account": income_account,
                "debit_in_account_currency": 0,
                "credit_in_account_currency": self.fine_amount,
                "company": self.company
            })

            je.insert(ignore_permissions=True)
            je.submit()
            
            # Update document with journal entry reference
            self.db_set("journal_entry", je.name)
            self.db_set("posted_to_gl", 1)
            self.db_set("posted_on", frappe.utils.now())
            frappe.db.commit()
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"SHG Meeting Fine - Failed to post to ledger: {self.name}")
            frappe.throw(_(f"Failed to post meeting fine to ledger: {str(e)}"))

    def get_fine_account(self, company):
        """Get fine income account, create if not exists"""
        try:
            from shg.shg.utils.account_utils import get_or_create_shg_penalty_income_account
            return get_or_create_shg_penalty_income_account(company)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"SHG Meeting Fine - Failed to get fine account for company {company}")
            frappe.throw(_(f"Failed to get fine account: {str(e)}"))
        
    def get_member_account(self):
        """Get member's ledger account"""
        try:
            member = frappe.get_doc("SHG Member", self.member)
            company = frappe.defaults.get_user_default("Company")
            if not company:
                companies = frappe.get_all("Company", limit=1)
                if companies:
                    company = companies[0].name
                    
            from shg.shg.utils.account_utils import get_or_create_member_account
            return get_or_create_member_account(member, company)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"SHG Meeting Fine - Failed to get member account for {self.member}")
            frappe.throw(_(f"Failed to get member account: {str(e)}"))
        
    def get_member_customer(self):
        """Get member's customer link with fallback"""
        try:
            member = frappe.get_doc("SHG Member", self.member)
            customer = member.customer
            # Implement fallback logic as per specification
            if not customer:
                # Fallback to member ID if no customer is linked
                customer = self.member
            return customer
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"SHG Meeting Fine - Failed to get member customer for {self.member}")
            # Fallback to member ID if all else fails
            return self.member
        
    @frappe.whitelist()
    def send_fine_notification(self):
        """Send fine notification to member"""
        from shg.shg.utils.notification_service import send_notification
        
        try:
            member = frappe.get_doc("SHG Member", self.member)
            
            message = f"Dear {member.member_name}, a fine of KES {self.fine_amount:,.2f} has been applied for {self.fine_reason.lower()}."
            
            # Send notification using the new service
            result = send_notification(
                member_id=self.member,
                notification_type="Meeting Fine",
                message=message,
                channel="SMS",
                reference_document="SHG Meeting Fine",
                reference_name=self.name
            )
            
            return result
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"SHG Meeting Fine - Failed to send fine notification for {self.name}")
            frappe.throw(_(f"Failed to send fine notification: {str(e)}"))


# --- Hook functions ---
# These are hook functions called from hooks.py and should NOT have @frappe.whitelist()
def validate_fine(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()


def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py - only post when status is 'Paid'"""
    try:
        if doc.docstatus == 1 and doc.status == "Paid" and not doc.get("posted_to_gl"):
            doc.post_to_ledger()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"SHG Meeting Fine - Failed to post to general ledger for {doc.name}")
        frappe.throw(_(f"Failed to post meeting fine to general ledger: {str(e)}"))