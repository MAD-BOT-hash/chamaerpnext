# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today, getdate
from frappe.desk.form.assign_to import add as assign_to

@frappe.whitelist()
def get_unpaid_invoices(filters=None):
    """Fetch all unpaid contribution invoices for selection"""
    # Base filters for unpaid invoices
    base_filters = {
        "status": ["in", ["Unpaid", "Partially Paid"]],
        "docstatus": 1
    }
    
    # Merge with provided filters
    if filters:
        base_filters.update(filters)
    
    invoices = frappe.get_all(
        "SHG Contribution Invoice",
        filters=base_filters,
        fields=[
            "name as invoice",
            "member",
            "member_name",
            "contribution_type",
            "invoice_date",
            "due_date",
            "amount",
            "paid_amount",
            "status"
        ]
    )
    
    # Calculate outstanding amount for each invoice
    for invoice in invoices:
        invoice["outstanding_amount"] = flt(invoice["amount"]) - flt(invoice["paid_amount"] or 0)
        invoice["payment_amount"] = invoice["outstanding_amount"]  # Default payment amount
        
    return invoices

class SHGMultiMemberPayment(Document):
    def validate(self):
        self.validate_payment_method()
        self.validate_duplicate_invoices()
        self.calculate_totals()
        self.set_default_account()
        self.validate_total_amount()
        
    def validate_payment_method(self):
        """Validate payment method is not 'Not Specified'"""
        if not self.payment_method or self.payment_method == "Not Specified":
            frappe.throw(_("Payment method cannot be 'Not Specified'. Please select a valid payment method."))
            
    def validate_duplicate_invoices(self):
        """Prevent duplicate invoices in the same payment entry"""
        invoice_names = [invoice.invoice for invoice in self.invoices]
        if len(invoice_names) != len(set(invoice_names)):
            frappe.throw(_("Duplicate invoices found. Each invoice can only be selected once."))
            
        # Check if any of these invoices are already part of another submitted payment
        for invoice_name in invoice_names:
            existing_payments = frappe.db.sql("""
                SELECT mp.name 
                FROM `tabSHG Multi Member Payment` mp
                INNER JOIN `tabSHG Multi Member Payment Invoice` mpi 
                ON mp.name = mpi.parent
                WHERE mpi.invoice = %s 
                AND mp.docstatus = 1
                AND mp.name != %s
            """, (invoice_name, self.name))
            
            if existing_payments:
                frappe.throw(_("Invoice {0} is already part of another submitted payment entry {1}.".format(
                    invoice_name, existing_payments[0][0])))
            
    def set_default_account(self):
        """Set default account based on payment method"""
        if not self.company or not self.payment_method:
            return
            
        if not self.account:
            # Get default account based on payment method from SHG Settings
            if self.payment_method == "Cash":
                self.account = frappe.db.get_value("SHG Settings", None, "default_cash_account")
            elif self.payment_method in ["Bank Transfer", "Mpesa"]:
                self.account = frappe.db.get_value("SHG Settings", None, "default_bank_account")
            else:
                # For other payment methods, use default debit account
                self.account = frappe.db.get_value("SHG Settings", None, "default_debit_account")
                
    def validate_total_amount(self):
        """Validate that total amount matches sum of invoice payments"""
        calculated_total = 0.0
        for invoice in self.invoices:
            calculated_total += flt(invoice.payment_amount)
            
        # Allow a small tolerance for floating point errors
        if abs(self.total_amount - calculated_total) > 0.01:
            frappe.throw(_("Total amount (KSh {0:,.2f}) does not match sum of invoice payments (KSh {1:,.2f}). Please verify the amounts.").format(
                self.total_amount, calculated_total))
            
    def calculate_totals(self):
        """Calculate total selected invoices and payment amount"""
        total_invoices = 0
        total_amount = 0.0
        
        for invoice in self.invoices:
            total_invoices += 1
            total_amount += flt(invoice.payment_amount or 0)
            
        self.total_selected_invoices = total_invoices
        self.total_payment_amount = total_amount
        self.total_amount = total_amount
        
    @frappe.whitelist()
    def get_unpaid_invoices(self):
        """Fetch all unpaid contribution invoices for selection"""
        invoices = frappe.get_all(
            "SHG Contribution Invoice",
            filters={
                "status": ["in", ["Unpaid", "Partially Paid"]],
                "docstatus": 1
            },
            fields=[
                "name as invoice",
                "member",
                "member_name",
                "contribution_type",
                "invoice_date",
                "due_date",
                "amount",
                "paid_amount",
                "status"
            ]
        )
        
        # Calculate outstanding amount for each invoice
        for invoice in invoices:
            invoice["outstanding_amount"] = flt(invoice["amount"]) - flt(invoice["paid_amount"] or 0)
            invoice["payment_amount"] = invoice["outstanding_amount"]  # Default payment amount
            
        return invoices
        
    def onload(self):
        """Set default values when loading the form"""
        if not self.company:
            self.company = frappe.db.get_single_value("SHG Settings", "company") or frappe.defaults.get_user_default("Company")
            
        if not self.payment_method:
            self.payment_method = frappe.db.get_single_value("SHG Settings", "default_payment_method") or "Cash"
            
    def on_submit(self):
        """Create Payment Entries for each selected invoice"""
        self.create_payment_entries()
        
    def create_payment_entries(self):
        """Create Payment Entries for each selected invoice"""
        try:
            for invoice_row in self.invoices:
                # Get the invoice document
                invoice = frappe.get_doc("SHG Contribution Invoice", invoice_row.invoice)
                
                # Validate that this invoice hasn't been fully paid
                if invoice.status == "Paid":
                    frappe.throw(_("Invoice {0} is already fully paid").format(invoice.name))
                
                # Get member account
                member_account = self.get_or_create_member_account(invoice.member, self.company)
                
                # Validate payment amount
                payment_amount = flt(invoice_row.payment_amount)
                if payment_amount <= 0:
                    frappe.throw(_("Payment amount must be greater than zero for invoice {0}").format(invoice.name))
                
                # Create Payment Entry
                pe = frappe.new_doc("Payment Entry")
                pe.payment_type = "Receive"
                pe.posting_date = self.payment_date
                pe.party_type = "Customer"
                pe.party = invoice.member  # Use member ID, not name
                pe.paid_amount = payment_amount
                pe.received_amount = payment_amount
                pe.payment_method = self.payment_method
                pe.company = self.company
                pe.reference_no = self.name
                pe.reference_date = self.payment_date
                pe.remarks = f"Payment for SHG Contribution Invoice {invoice.name}"
                
                # Set accounts correctly for receive payment
                pe.paid_to = self.account  # Debit to bank/cash account
                pe.paid_from = member_account  # Credit from member account
                
                # Add reference to the invoice
                pe.append("references", {
                    "reference_doctype": "SHG Contribution Invoice",
                    "reference_name": invoice.name,
                    "allocated_amount": payment_amount,
                    "total_amount": flt(invoice.amount),
                    "outstanding_amount": flt(invoice.amount) - flt(invoice.paid_amount or 0)
                })
                
                # Insert and submit the Payment Entry
                pe.insert(ignore_permissions=True)
                pe.submit()
                
                # Update invoice status
                paid_amount = payment_amount
                outstanding_amount = flt(invoice.amount) - flt(invoice.paid_amount or 0)
                
                if paid_amount >= outstanding_amount:
                    invoice.db_set("status", "Paid")
                else:
                    invoice.db_set("status", "Partially Paid")
                    
                # Update paid amount on invoice
                new_paid_amount = flt(invoice.paid_amount or 0) + paid_amount
                invoice.db_set("paid_amount", new_paid_amount)
                
                # Update linked contribution if exists
                if invoice.linked_shg_contribution:
                    contribution = frappe.get_doc("SHG Contribution", invoice.linked_shg_contribution)
                    contribution.update_payment_status(paid_amount)
                    
                # Update the payment reference on the invoice
                invoice.db_set("payment_reference", pe.name)
                
            frappe.msgprint(_("✅ Payments recorded successfully for {0} invoices (Total: KSh {1:,.2f}).").format(
                len(self.invoices), self.total_payment_amount))
                
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SHG Multi Member Payment Creation Failed")
            frappe.throw(_("Failed to create payment entries: {0}").format(str(e)))
            
    def get_or_create_member_account(self, member_id, company):
        """Ensure member has a personal ledger account under SHG Members."""
        parent_account = frappe.db.get_value(
            "Account", {"account_name": f"SHG Members - {company}", "company": company, "is_group": 1}, "name"
        )
        if not parent_account:
            # Try to find any receivable parent account
            parent_account = frappe.db.get_value(
                "Account", {"account_type": "Receivable", "company": company, "is_group": 1}, "name"
            )
            if not parent_account:
                frappe.throw(_(f"Parent account 'SHG Members - {company}' not found. Please create it under Accounts Receivable."))

        member_account = frappe.db.exists("Account", {"account_name": f"{member_id} - {company}", "company": company})
        if member_account:
            return member_account

        # Auto-create member sub-account
        acc = frappe.get_doc({
            "doctype": "Account",
            "account_name": f"{member_id} - {company}",
            "parent_account": parent_account,
            "is_group": 0,
            "company": company,
            "account_type": "Receivable"
        })
        acc.insert(ignore_permissions=True)
        frappe.msgprint(_(f"Created ledger account for {member_id}"))
        return acc.name