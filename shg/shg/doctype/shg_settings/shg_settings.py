import frappe
from frappe.model.document import Document

class SHGSettings(Document):
    def validate(self):
        """Validate SHG settings"""
        if self.default_contribution_amount < 0:
            frappe.throw("Default contribution amount cannot be negative")
            
        if self.default_interest_rate < 0 or self.default_interest_rate > 100:
            frappe.throw("Interest rate must be between 0 and 100 percent")
            
        if self.penalty_rate < 0 or self.penalty_rate > 100:
            frappe.throw("Penalty rate must be between 0 and 100 percent")
            
        # Validate Mpesa settings if enabled
        if self.mpesa_enabled:
            if not self.mpesa_consumer_key:
                frappe.throw("Mpesa Consumer Key is required")
            if not self.mpesa_consumer_secret:
                frappe.throw("Mpesa Consumer Secret is required")
            if not self.mpesa_shortcode:
                frappe.throw("Mpesa Shortcode is required")
            if not self.mpesa_passkey:
                frappe.throw("Mpesa Passkey is required")
            
        # Validate email settings if monthly statements are enabled
        if self.enable_monthly_statements:
            if not self.statement_sender_email:
                frappe.throw("Statement Sender Email is required when monthly statements are enabled")
            if not self.statement_email_subject:
                frappe.throw("Statement Email Subject is required when monthly statements are enabled")
            if not self.statement_email_template:
                frappe.throw("Statement Email Template is required when monthly statements are enabled")
            
        # Validate accounting settings
        if self.default_bank_account and not frappe.db.exists("Account", self.default_bank_account):
            frappe.throw("Default Bank Account does not exist")
        if self.default_cash_account and not frappe.db.exists("Account", self.default_cash_account):
            frappe.throw("Default Cash Account does not exist")
        if self.default_loan_account and not frappe.db.exists("Account", self.default_loan_account):
            frappe.throw("Default Loan Account does not exist")
        if self.default_interest_income_account and not frappe.db.exists("Account", self.default_interest_income_account):
            frappe.throw("Default Interest Income Account does not exist")
            
        # Validate receive payment settings
        if self.default_debit_account and not frappe.db.exists("Account", self.default_debit_account):
            frappe.throw("Default Debit Account does not exist")
        if self.default_credit_account and not frappe.db.exists("Account", self.default_credit_account):
            frappe.throw("Default Credit Account does not exist")
        
        # Validate member account settings
        if self.default_parent_ledger and not frappe.db.exists("Account", self.default_parent_ledger):
            frappe.throw("Default Parent Ledger does not exist")