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
        self.fetch_member_account_number()
        
    def before_validate(self):
        """Ensure company is populated from SHG Settings."""
        from shg.shg.utils.company_utils import get_default_company
        if not getattr(self, "company", None):
            default_company = get_default_company()
            if default_company:
                self.company = default_company
            else:
                frappe.throw("Please set Default Company in SHG Settings before continuing.")

    def fetch_member_account_number(self):
        """Fetch account number from member document"""
        if self.member and not self.account_number:
            member = frappe.get_doc("SHG Member", self.member)
            if member.account_number:
                self.account_number = member.account_number
        
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
        self.update_linked_invoices()

    def on_cancel(self):
        """Reopen invoices when payment entry is cancelled"""
        self.reopen_linked_invoices()
        
    def process_payment(self):
        """Process the payment and update related records with proper ERPNext v15 logic"""
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
                
                elif entry.invoice_type == "SHG Meeting Fine":
                    # Handle fine payment
                    self.process_fine_payment(entry)
                
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
            
    def process_fine_payment(self, entry):
        """Process payment for a meeting fine"""
        try:
            # Get the SHG Meeting Fine
            fine = frappe.get_doc("SHG Meeting Fine", entry.reference_name)
            
            # Mark fine as paid
            fine.status = "Paid"
            fine.paid_date = self.payment_date
            fine.flags.ignore_validate_update_after_submit = True
            fine.save()
            
            # Post to GL
            self.post_fine_to_general_ledger(entry, fine)
            
            frappe.msgprint(f"Fine {fine.name} marked as Paid")
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"SHG Fine Payment Processing Failed for {entry.reference_name}")
            frappe.throw(_("Failed to process fine payment: {0}").format(str(e)))
            
    def post_fine_to_general_ledger(self, entry, fine):
        """Post fine payment to general ledger"""
        try:
            company = self.company or frappe.db.get_single_value("SHG Settings", "company") or frappe.defaults.get_user_default("Company")
            if not company:
                frappe.throw(_("Company not set for this transaction"))
                
            # Get member account with auto-creation if needed
            from shg.shg.utils.account_utils import get_or_create_member_account
            member = frappe.get_doc("SHG Member", fine.member)
            member_account = get_or_create_member_account(member, company)
            
            # Get fine income account
            fine_account = fine.get_fine_account(company)
            
            # Get member customer with fallback
            member_customer = fine.get_member_customer()
            if not member_customer:
                # Fallback to member ID if no customer is linked
                member_customer = fine.member
            
            # Create Journal Entry for the fine payment
            je = frappe.new_doc("Journal Entry")
            je.voucher_type = "Journal Entry"
            je.posting_date = self.payment_date
            je.company = company
            je.remark = f"Payment for Meeting Fine {fine.name}"
            
            # Debit: Fine Income Account
            je.append("accounts", {
                "account": fine_account,
                "debit_in_account_currency": entry.amount,
                "credit_in_account_currency": 0,
                "party_type": "Customer",
                "party": member_customer,
                "reference_type": "SHG Meeting Fine",
                "reference_name": fine.name
            })
            
            # Credit: Member Account
            je.append("accounts", {
                "account": member_account,
                "debit_in_account_currency": 0,
                "credit_in_account_currency": entry.amount,
                "party_type": "Customer",
                "party": member_customer,
                "reference_type": "SHG Meeting Fine",
                "reference_name": fine.name
            })
            
            je.flags.ignore_mandatory = True
            je.insert(ignore_permissions=True)
            je.submit()
            
            # Link the journal entry to the fine
            fine.db_set("journal_entry", je.name)
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"SHG Fine GL Posting Failed for {entry.reference_name}")
            frappe.throw(_("Failed to post fine to GL: {0}").format(str(e)))

    def update_member_summary(self):
        """Update member financial summary with proper ERPNext v15 logic"""
        member = frappe.get_doc("SHG Member", self.member)
        
        # Update total contributions
        current_contributions = member.total_contributions or 0
        member.db_set("total_contributions", current_contributions + self.total_amount)
        
        # Update total payments received
        current_payments = member.total_payments_received or 0
        member.db_set("total_payments_received", current_payments + self.total_amount)
        
        # Update last contribution date
        member.db_set("last_contribution_date", self.payment_date)
        
        # Recalculate member's financial summary to ensure consistency
        member.update_financial_summary()

    def update_linked_invoices(self):
        """Update SHG Contribution Invoices as Paid and Closed after payment submission"""
        try:
            # Safety check
            if not self.name:
                return
                
            # Loop through allocated references in payment entry
            for entry in self.payment_entries:
                if entry.invoice_type == "SHG Contribution Invoice" and entry.invoice:
                    # Safety check: ensure invoice exists
                    if frappe.db.exists("SHG Contribution Invoice", entry.invoice):
                        invoice = frappe.get_doc("SHG Contribution Invoice", entry.invoice)
                        
                        # Update status and close the invoice
                        invoice.db_set("status", "Paid", update_modified=False)
                        if frappe.db.has_column("SHG Contribution Invoice", "is_closed"):
                            invoice.db_set("is_closed", 1, update_modified=False)
                        else:
                            # Try to set via custom field
                            try:
                                invoice.db_set("is_closed", 1, update_modified=False)
                            except Exception:
                                pass  # Field might not exist yet
                        
                        # Mark linked contribution as paid
                        invoice.mark_linked_contribution_as_paid()

                        frappe.db.commit()
                        frappe.msgprint(f"✅ Invoice {invoice.name} marked as Paid and Closed")

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to update invoices after SHG Payment Entry submission: {self.name}")
            frappe.throw("Failed to update related invoices. Please check system logs.")

    def reopen_linked_invoices(self):
        """Reopen SHG Contribution Invoices when payment entry is cancelled"""
        try:
            # Safety check
            if not self.name:
                return
                
            # Loop through allocated references in payment entry
            for entry in self.payment_entries:
                if entry.invoice_type == "SHG Contribution Invoice" and entry.invoice:
                    # Safety check: ensure invoice exists
                    if frappe.db.exists("SHG Contribution Invoice", entry.invoice):
                        invoice = frappe.get_doc("SHG Contribution Invoice", entry.invoice)
                        
                        # Reopen the invoice
                        invoice.db_set("status", "Unpaid", update_modified=False)
                        if frappe.db.has_column("SHG Contribution Invoice", "is_closed"):
                            invoice.db_set("is_closed", 0, update_modified=False)
                        else:
                            # Try to set via custom field
                            try:
                                invoice.db_set("is_closed", 0, update_modified=False)
                            except Exception:
                                pass  # Field might not exist yet
                        
                        # Reopen linked contribution
                        invoice.reopen_linked_contribution()

                        frappe.db.commit()
                        frappe.msgprint(f"✅ Invoice {invoice.name} reopened")

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to reopen invoices after SHG Payment Entry cancellation: {self.name}")
            frappe.throw("Failed to reopen related invoices. Please check system logs.")

# ----------------------
# API endpoint for dialog
# ----------------------

@frappe.whitelist()
def get_unpaid_fines(member):
    """Fetch all unpaid SHG Meeting Fines for a member."""
    fines = frappe.get_all(
        "SHG Meeting Fine",
        filters={"member": member, "status": ["!=", "Paid"]},
        fields=["name", "fine_date", "fine_reason", "fine_amount", "fine_description"],
        order_by="fine_date desc",
    )
    return fines

def update_invoice_status(invoice_name, paid_amount):
    """
    Update contribution invoice status after payment with proper ERPNext v15 logic
    
    Args:
        invoice_name (str): SHG Contribution Invoice name
        paid_amount (float): Amount paid
    """
    try:
        # Safety check
        if not invoice_name:
            return
            
        # Safety check: ensure invoice exists
        if not frappe.db.exists("SHG Contribution Invoice", invoice_name):
            return
            
        # Get the invoice
        invoice = frappe.get_doc("SHG Contribution Invoice", invoice_name)
        
        if invoice.sales_invoice:
            # Update linked Sales Invoice
            sales_invoice = frappe.get_doc("Sales Invoice", invoice.sales_invoice)
            new_outstanding = sales_invoice.outstanding_amount - paid_amount
            
            # Ensure we don't go below zero
            new_outstanding = max(0, new_outstanding)
            sales_invoice.db_set("outstanding_amount", new_outstanding)
            
            # Update invoice status based on outstanding amount
            if new_outstanding <= 0:
                invoice.db_set("status", "Paid")
                # Also update the Sales Invoice status
                sales_invoice.db_set("status", "Paid")
                # Auto-close the invoice
                invoice.db_set("is_closed", 1)
                # Mark linked contribution as paid
                invoice.mark_linked_contribution_as_paid()
                frappe.logger().info(f"Invoice {invoice_name} marked as closed after full payment")
            elif new_outstanding < sales_invoice.grand_total:
                invoice.db_set("status", "Partially Paid")
                # Also update the Sales Invoice status
                sales_invoice.db_set("status", "Partially Paid")
                # Reopen linked contribution if needed
                invoice.reopen_linked_contribution()
            else:
                invoice.db_set("status", "Unpaid")
                # Also update the Sales Invoice status
                sales_invoice.db_set("status", "Unpaid")
                # Reopen linked contribution if needed
                invoice.reopen_linked_contribution()
                
        # Update member financial summary
        member = frappe.get_doc("SHG Member", invoice.member)
        total_unpaid = (member.total_unpaid_contributions or 0) - paid_amount
        member.db_set("total_unpaid_contributions", max(0, total_unpaid))
        
        # Recalculate member's financial summary to ensure consistency
        member.update_financial_summary()
        
        # Reload the invoice to reflect changes
        invoice.reload()
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Update Invoice Status Failed for invoice {invoice_name}")
        frappe.throw(_("Failed to update invoice status: {0}").format(str(e)))