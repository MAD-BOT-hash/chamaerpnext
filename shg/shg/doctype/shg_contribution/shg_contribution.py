import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate, getdate, formatdate
from frappe.utils import flt
from typing import Dict, List, Optional

class SHGContribution(Document):
    """
    SHG Contribution DocType - Business Layer
    
    NOTE: This is an SHG Business Layer document.
    It should NEVER be added as a Payment Entry reference.
    Payment Entry = Accounting Layer (ERPNext standard)
    SHGContribution = Business Layer (SHG custom)
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Import services - lazy import to avoid circular dependencies
        from shg.shg.services.services import get_service
        self.contribution_service = get_service('contribution')
        self.member_service = get_service('member')
        self.notification_service = get_service('notification')
        self.logger = frappe.logger("shg_contribution", allow_site=True)
    
    def validate(self):
        """Validate contribution - all business logic in service layer"""
        self._validate_amount()
        self._validate_duplicate()
        self._validate_contribution_type()
        self._validate_posting_date()
        self._ensure_amount_precision()
    
    def before_validate(self):
        """Ensure company is populated from SHG Settings"""
        from shg.shg.utils.company_utils import get_default_company
        if not getattr(self, "company", None):
            default_company = get_default_company()
            if default_company:
                self.company = default_company
            else:
                frappe.throw("Please set Default Company in SHG Settings before continuing.")
    
    def on_submit(self):
        """Handle submission - delegate to service layer"""
        try:
            # Post to ledger through accounting service
            if not self.get("posted_to_gl"):
                self._post_to_ledger()
            
            # Update member summary
            self._update_member_summary()
            
            # Log successful submission
            self._log_submission()
            
        except Exception as e:
            self.logger.error(f"Contribution submission failed: {str(e)}")
            frappe.throw(f"Contribution submission failed: {str(e)}")
    
    def on_cancel(self):
        """Handle cancellation - delegate to service layer"""
        try:
            self._cancel_journal_entry()
            self._update_member_summary()
            self._log_cancellation()
        except Exception as e:
            self.logger.error(f"Contribution cancellation failed: {str(e)}")
            frappe.throw(f"Cancellation failed: {str(e)}")
    
    def _validate_amount(self):
        """Validate contribution amount"""
        amount = flt(self.amount)
        if amount <= 0:
            frappe.throw(_("Contribution amount must be greater than zero"))
    
    def _validate_duplicate(self):
        """Check for duplicate contributions using service layer"""
        # Service layer handles duplicate prevention with proper locking
        pass  # Service layer handles this
    
    def _validate_contribution_type(self):
        """Validate contribution type"""
        if self.contribution_type:
            if not frappe.db.exists("SHG Contribution Type", self.contribution_type):
                frappe.throw(_(f"Invalid contribution type: {self.contribution_type}"))
    
    def _validate_posting_date(self):
        """Validate posting date against locked periods"""
        from shg.shg.utils.posting_locks import validate_posting_date
        posting_date = self.posting_date or self.contribution_date
        if posting_date:
            validate_posting_date(posting_date)
    
    def _ensure_amount_precision(self):
        """Ensure proper decimal precision for all amount fields"""
        if self.amount:
            self.amount = round(flt(self.amount), 2)
        if self.expected_amount:
            self.expected_amount = round(flt(self.expected_amount), 2)
        if self.amount_paid:
            self.amount_paid = round(flt(self.amount_paid), 2)
        if self.unpaid_amount:
            self.unpaid_amount = round(flt(self.unpaid_amount), 2)
    
    def _post_to_ledger(self):
        """Post contribution to ledger through accounting service"""
        from shg.shg.services.services import get_service
        gl_service = get_service('accounting')
        
        # Prepare journal entry data
        je_data = self._prepare_journal_entry_data()
        
        # Create journal entry through service
        je_name = gl_service.create_journal_entry(je_data)
        
        # Update contribution with journal entry reference
        self.db_set("journal_entry", je_name)
        self.db_set("posted_to_gl", 1)
        self.db_set("posted_on", frappe.utils.now())
    
    def _prepare_journal_entry_data(self) -> Dict:
        """Prepare data for journal entry creation"""
        # Get member account
        member_account = self._get_member_account()
        
        # Get income account
        income_account = self._get_income_account()
        
        return {
            "company": self.company,
            "posting_date": self.contribution_date or nowdate(),
            "accounts": [
                {
                    "account": member_account,
                    "party_type": "Customer",
                    "party": self.get("customer") or self._get_customer(),
                    "debit_in_account_currency": self.amount,
                    "credit_in_account_currency": 0
                },
                {
                    "account": income_account,
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": self.amount
                }
            ],
            "voucher_type": "Journal Entry",
            "voucher_no": self.name,
            "remarks": f"Contribution from {self.member_name}"
        }
    
    def _get_member_account(self) -> str:
        """Get member ledger account through member service"""
        return self.member_service.create_member_account(self.member, self.company)
    
    def _get_income_account(self) -> str:
        """Get appropriate income account"""
        # Get from settings or default
        settings_income = frappe.db.get_single_value("SHG Settings", "default_income_account")
        if settings_income:
            return settings_income
        
        # Get company abbreviation
        company_abbr = frappe.db.get_value("Company", self.company, "abbr")
        
        # Try to find contributions income account
        income_account = frappe.db.get_value("Account", {
            "account_name": f"SHG Contributions - {company_abbr}",
            "company": self.company
        })
        
        if income_account:
            return income_account
        
        # Fallback to generic income account
        income_parent = frappe.db.get_value("Account", {
            "account_name": "Income",
            "company": self.company,
            "is_group": 1
        })
        
        if income_parent:
            # Create contributions account if it doesn't exist
            contributions_account = frappe.get_doc({
                "doctype": "Account",
                "account_name": f"SHG Contributions - {company_abbr}",
                "company": self.company,
                "parent_account": income_parent,
                "is_group": 0,
                "account_type": "Income Account",
                "root_type": "Income",
                "report_type": "Profit and Loss"
            })
            contributions_account.insert(ignore_permissions=True)
            return contributions_account.name
        
        frappe.throw("No income account found for this company")
    
    def _get_customer(self) -> str:
        """Get customer linked to member"""
        customer = frappe.db.get_value("SHG Member", self.member, "customer")
        if not customer:
            frappe.throw(f"No customer linked to member {self.member}")
        return customer
    
    def _update_member_summary(self):
        """Update member financial summary through member service"""
        try:
            self.member_service.update_member_financial_summary(self.member)
        except Exception as e:
            self.logger.error(f"Failed to update member summary: {str(e)}")
    
    def _cancel_journal_entry(self):
        """Cancel associated journal entry"""
        if self.journal_entry:
            je = frappe.get_doc("Journal Entry", self.journal_entry)
            if je.docstatus == 1:
                je.cancel()
    
    def _log_submission(self):
        """Log successful submission"""
        try:
            log_entry = frappe.get_doc({
                'doctype': 'SHG Contribution Log',
                'contribution': self.name,
                'member': self.member,
                'amount': self.amount,
                'status': 'Submitted',
                'action': 'Submit',
                'timestamp': frappe.utils.now()
            })
            log_entry.insert(ignore_permissions=True)
        except Exception as e:
            self.logger.error(f"Failed to log submission: {str(e)}")
    
    def _log_cancellation(self):
        """Log cancellation"""
        try:
            log_entry = frappe.get_doc({
                'doctype': 'SHG Contribution Log',
                'contribution': self.name,
                'member': self.member,
                'amount': self.amount,
                'status': 'Cancelled',
                'action': 'Cancel',
                'timestamp': frappe.utils.now()
            })
            log_entry.insert(ignore_permissions=True)
        except Exception as e:
            self.logger.error(f"Failed to log cancellation: {str(e)}")
    
    @frappe.whitelist()
    def update_payment_status(self, payment_amount: float, payment_entry_name: Optional[str] = None):
        """
        Update payment status through service layer
        This is the main entry point for payment processing
        """
        try:
            # Validate payment amount doesn't exceed unpaid amount
            payment_amount = flt(payment_amount)
            if payment_amount <= 0:
                frappe.throw(_("Payment amount must be greater than zero"))
            
            unpaid_amount = flt(self.unpaid_amount or (self.expected_amount or self.amount))
            if payment_amount > unpaid_amount:
                frappe.throw(_("Payment amount cannot exceed unpaid amount"))
            
            # Process payment through service layer
            result = self.contribution_service.update_payment_status(
                self.name, 
                payment_amount, 
                payment_entry_name
            )
            
            # Send payment confirmation
            self._send_payment_confirmation(payment_amount)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Payment status update failed: {str(e)}")
            frappe.throw(f"Payment processing failed: {str(e)}")
    
    def _send_payment_confirmation(self, payment_amount: float):
        """Send payment confirmation notification"""
        try:
            message = f"""
            Dear {self.member_name},
            
            Your payment of KES {payment_amount:,.2f} for contribution {self.name} 
            has been successfully recorded.
            
            Thank you for your continued support.
            
            SHG Management
            """
            
            self.notification_service.send_notification(
                self.member,
                'Payment Confirmation',
                message,
                'SMS'
            )
        except Exception as e:
            self.logger.error(f"Failed to send payment confirmation: {str(e)}")

# Service layer functions - for backward compatibility with hooks
@frappe.whitelist()
def validate_contribution(doc, method):
    """Hook function called from hooks.py"""
    # All validation now handled in class methods
    pass

@frappe.whitelist() 
def post_to_general_ledger(doc, method):
    """Hook function called from hooks.py"""
    # All ledger posting now handled in class methods
    pass

def create_contribution_from_invoice(doc, method=None):
    """Create contribution from invoice using service layer"""
    from shg.shg.services.services import get_service
    contribution_service = get_service('contribution')
    
    try:
        contribution_data = {
            "member": doc.member,
            "member_name": doc.member_name,
            "contribution_date": doc.invoice_date,
            "posting_date": doc.invoice_date,
            "amount": flt(doc.amount),
            "expected_amount": flt(doc.amount),
            "contribution_type": doc.contribution_type,
            "invoice_reference": doc.name,
            "description": f"Auto-created from invoice {doc.name}",
            "auto_submit": True
        }
        
        result = contribution_service.create_contribution(contribution_data)
        return frappe.get_doc("SHG Contribution", result['name'])
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Contribution creation from invoice failed")
        return None

def update_overdue_contributions():
    """Update overdue contributions using scheduler service"""
    from shg.shg.services.services import get_service
    scheduler_service = get_service('scheduler')
    
    try:
        return scheduler_service.process_overdue_contributions()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Overdue contributions processing failed")
        return None
