# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today
from shg.shg.utils.payment import update_invoice_status, send_payment_receipt

class SHGPaymentEntry(Document):
    def validate(self):
        self.validate_payment_entries()
        self.calculate_total_amount()
        
    def validate_payment_entries(self):
        """Validate payment entries"""
        if not self.payment_entries:
            frappe.throw(_("At least one payment entry is required"))
            
        total = 0
        for entry in self.payment_entries:
            if entry.amount <= 0:
                frappe.throw(_("Payment amount must be greater than zero"))
            total += entry.amount
            
        self.total_amount = total
        
    def calculate_total_amount(self):
        """Calculate total payment amount"""
        total = 0
        for entry in self.payment_entries:
            total += entry.amount
        self.total_amount = total
        
    def on_submit(self):
        """Process payment on submission"""
        self.process_payment()
        
    def process_payment(self):
        """Process the payment and update related records"""
        try:
            # Update each invoice
            for entry in self.payment_entries:
                if entry.invoice_type == "SHG Contribution Invoice":
                    update_invoice_status(entry.invoice, entry.amount)
                    
            # Update member financial summary
            self.update_member_summary()
            
            # Send email receipt if enabled
            if frappe.db.get_single_value("SHG Settings", "auto_email_receipt"):
                send_payment_receipt(self)
                
            frappe.msgprint(_("Payment processed successfully"))
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Payment Entry Processing Failed")
            frappe.throw(_("Failed to process payment: {0}").format(str(e)))
            
    def update_member_summary(self):
        """Update member financial summary"""
        member = frappe.get_doc("SHG Member", self.member)
        
        # Update total contributions
        member.db_set("total_contributions", member.total_contributions + self.total_amount)
        
        # Update last contribution date
        member.db_set("last_contribution_date", self.payment_date)
        
    def send_payment_receipt(self):
        """Send payment receipt via email"""
        try:
            member = frappe.get_doc("SHG Member", self.member)
            
            if not member.email:
                return
                
            # Prepare email content
            subject = f"Payment Receipt - {self.name}"
            
            message = f"""Dear {self.member_name},

Thank you for your payment. Here are the details:

Payment Reference: {self.name}
Payment Date: {self.payment_date}
Total Amount: KES {self.total_amount:,.2f}
Payment Method: {self.payment_method}

Payment Details:
"""
            
            for entry in self.payment_entries:
                message += f"- Invoice {entry.invoice}: KES {entry.amount:,.2f}\n"
                
            message += """

Thank you for your continued support.

SHG Management"""
            
            # Send email
            frappe.sendmail(
                recipients=[member.email],
                subject=subject,
                message=message
            )
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Payment Receipt Email Failed")