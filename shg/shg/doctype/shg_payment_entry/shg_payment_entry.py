# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today
from shg.shg.utils.payment import update_invoice_status, send_payment_receipt, create_payment_entry_for_invoice

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
            created_payment_entries = []
            
            # Create Payment Entry for each invoice
            for entry in self.payment_entries:
                if entry.invoice_type == "SHG Contribution Invoice":
                    # Get the SHG Contribution Invoice
                    shg_invoice = frappe.get_doc("SHG Contribution Invoice", entry.invoice)
                    
                    if shg_invoice.sales_invoice:
                        # Create Payment Entry for the Sales Invoice
                        payment_entry_name = create_payment_entry_for_invoice(
                            shg_invoice.sales_invoice,
                            entry.amount,
                            self.payment_date,
                            self.member
                        )
                        created_payment_entries.append(payment_entry_name)
                        
                        # Update invoice status
                        update_invoice_status(entry.invoice, entry.amount)
                
            # Link created Payment Entries to this SHG Payment Entry
            if created_payment_entries:
                self.db_set("created_payment_entries", ", ".join(created_payment_entries))
            
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
        
        # Update total payments received
        current_payments = member.total_payments_received or 0
        member.db_set("total_payments_received", current_payments + self.total_amount)
        
        # Update last contribution date
        member.db_set("last_contribution_date", self.payment_date)